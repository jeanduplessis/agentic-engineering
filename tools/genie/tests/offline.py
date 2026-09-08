"""Bounded fake-process and PTY checks. No installed Pi or model is reachable."""
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

BINARY = str(Path(sys.argv.pop(1)).resolve())
PRELUDE = '''import json, os, signal, subprocess, sys, time
from pathlib import Path
root = Path(os.environ["FIXTURE"])
def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)
def final(text="final", stop="stop"):
    emit({"type":"message_end", "message":{"role":"assistant", "stopReason":stop, "content":[{"type":"text","text":text}]}})
def gate(name):
    (root / (name + ".ready")).touch()
    deadline = time.monotonic() + 6
    while not (root / name).exists():
        if time.monotonic() > deadline: raise RuntimeError("fixture gate timed out")
        time.sleep(.005)
'''


def wait_until(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("fixture deadline expired")
        time.sleep(.005)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class Offline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="genie-offline-")
        self.root = Path(self.temp.name)
        for name in ["bin", "home", "state"]:
            (self.root / name).mkdir()
        self.env = {
            "PATH": str(self.root / "bin"), "HOME": str(self.root / "home"),
            "PI_CODING_AGENT_DIR": str(self.root / "state"),
            "PI_AGENT_DIR": str(self.root / "state"), "FIXTURE": str(self.root),
            "TERM": "xterm-256color",
        }
        self.children = []
        self.masters = []

    def tearDown(self):
        # Fixtures record their owned groups so even a failed assertion is bounded.
        for file in self.root.glob("*.pid"):
            try:
                os.killpg(int(file.read_text()), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=4)
        for master in self.masters:
            os.close(master)
        self.temp.cleanup()

    def fake(self, body):
        (self.root / "pi.pid").unlink(missing_ok=True)
        path = self.root / "bin" / "pi"
        path.write_text("#!" + sys.executable + "\n" + PRELUDE + '\n(root / "pi.pid").write_text(str(os.getpid()))\n' + body)
        path.chmod(0o700)

    def start(self, *args, tty=False, shared=False, columns=80):
        stderr = subprocess.PIPE
        stdout = subprocess.PIPE
        master = None
        if tty:
            master, slave = pty.openpty()
            self.masters.append(master)
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, columns, 0, 0))
            stderr = slave
            if shared:
                stdout = slave
        child = subprocess.Popen([BINARY, *args, "inspect"], env=self.env, cwd=self.root,
                                 stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        self.children.append(child)
        if tty:
            os.close(slave)
        return child, master

    def run_fake(self, body, *args):
        self.fake(body)
        child, _ = self.start(*args)
        out, err = child.communicate(timeout=7)
        return child.returncode, out, err

    def ready(self, name):
        wait_until(lambda: (self.root / (name + ".ready")).exists())

    def release(self, name):
        (self.root / name).touch()

    def read_pty(self, master, until=None, timeout=4):
        data = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if select.select([master], [], [], .05)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                data.extend(chunk)
                if until is not None and until in data:
                    return bytes(data)
        if until is not None:
            self.assertIn(until, data)
        return bytes(data)

    def test_final_only_across_late_turns_and_eof(self):
        self.fake('''emit({"type":"session"})
final("old")
emit({"type":"agent_end", "willRetry":False})
emit({"type":"agent_settled"})
gate("late")
emit({"type":"agent_start"})
emit({"type":"message_update", "assistantMessageEvent":{"type":"thinking_delta", "delta":"PRIVATE"}})
emit({"type":"message_end", "message":{"role":"toolResult","content":"PRIVATE"}})
emit({"type":"future_event","secret":"PRIVATE"})
record = {"type":"message_end", "message":{"role":"assistant", "stopReason":"stop", "content":[{"type":"thinking","thinking":"PRIVATE"},{"type":"text","text":"🧞 first"},{"type":"text","text":"second\\n"}]}}
for byte in json.dumps(record, ensure_ascii=False).encode():
    os.write(1, bytes([byte]))
gate("exit")
''')
        child, _ = self.start()
        self.ready("late")
        self.assertEqual(select.select([child.stdout], [], [], 0)[0], [])
        self.release("late")
        self.ready("exit")
        self.assertEqual(select.select([child.stdout], [], [], 0)[0], [])
        self.release("exit")
        out, err = child.communicate(timeout=6)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(out, "🧞 first\nsecond\n\n".encode())
        self.assertEqual(err, b"")

    def test_outcomes_and_private_protocol_failures(self):
        cases = [
            ('final("discard"); sys.exit(37)', 37, b"", None),
            ('final("old"); final("PRIVATE", "error")', 1, b"", b"error"),
            ('final("old"); final("PRIVATE", "aborted")', 1, b"", b"aborted"),
            ('final("old"); emit({"type":"agent_start"})', 1, b"", b"no final"),
            ('emit({"type":"session"})', 1, b"", b"no final"),
            ('final("PRIVATE", "toolUse")', 1, b"", b"unresolved"),
            ('final("partial", "length")', 0, b"partial\n", b"truncated"),
            ('final("old", "length"); final("new")', 0, b"new\n", None),
            ('final("old"); emit({"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[]}})', 0, b"", None),
            ('final("old"); emit({"type":"auto_retry_start"}); emit({"type":"auto_retry_end","success":False,"finalError":"Retry cancelled"})', 1, b"", b"retry"),
            ('print("PRIVATE truncated {", flush=True)', None, b"", b"invalid Pi JSON"),
            ('os.write(1, b"x" * (8 * 1024 * 1024 + 1))', None, b"", b"8 MiB"),
        ]
        for body, code, stdout, error in cases:
            with self.subTest(body=body):
                status, out, err = self.run_fake(body)
                if code is None:
                    self.assertNotEqual(status, 0)
                else:
                    self.assertEqual(status, code)
                self.assertEqual(out, stdout)
                self.assertNotIn(b"PRIVATE", err)
                if error:
                    self.assertIn(error, err)

    def test_only_final_assistant_error_diagnostic_is_published_even_when_quiet(self):
        error = {"type": "message_end", "message": {"role": "assistant", "stopReason": "error",
                 "content": [{"type": "text", "text": "PRIVATE RESPONSE"}],
                 "errorMessage": "Provider rate limit: try later"}}
        for stop in ["error", "aborted"]:
            error["message"]["stopReason"] = stop
            status, out, err = self.run_fake("emit(" + repr(error) + ")", "--quiet")
            self.assertEqual(status, 1)
            self.assertEqual(out, b"")
            self.assertEqual(err, b"g: Provider rate limit: try later\n")
        status, out, err = self.run_fake("emit(" + repr(error) + "); final('recovered')")
        self.assertEqual((status, out, err), (0, b"recovered\n", b""))
        error["message"]["errorMessage"] = "x" * 5000 + "PRIVATE TAIL"
        status, out, err = self.run_fake("emit(" + repr(error) + ")")
        self.assertEqual(status, 1)
        self.assertEqual(out, b"")
        self.assertEqual(err, b"g: " + b"x" * 4096 + b"\n")

    def test_exhausted_retry_reports_authoritative_terminal_error(self):
        initial = {"type": "message_end", "message": {"role": "assistant", "stopReason": "error",
                   "content": [], "errorMessage": "PRIVATE recovered error"}}
        terminal = {"type": "message_end", "message": {"role": "assistant", "stopReason": "error",
                    "content": [{"type": "text", "text": "PRIVATE RESPONSE"}],
                    "errorMessage": "Provider quota exhausted: contact administrator"}}
        # Pi agent-session.js emits the final error first, then failed retry end.
        events = [
            {"type": "agent_start"}, initial,
            {"type": "agent_end", "willRetry": True},
            {"type": "auto_retry_start", "attempt": 1},
            {"type": "agent_start"}, terminal,
            {"type": "agent_end", "willRetry": False},
            {"type": "auto_retry_end", "success": False, "finalError": "PRIVATE summary"},
            {"type": "agent_settled"},
        ]
        body = "\n".join("emit(" + repr(event) + ")" for event in events)
        status, out, err = self.run_fake(body, "-q")
        self.assertEqual((status, out, err), (1, b"", b"g: Provider quota exhausted: contact administrator\n"))
        status, out, err = self.run_fake(body + '\nemit({"type":"agent_start"}); final("recovered")')
        self.assertEqual((status, out, err), (0, b"recovered\n", b""))
        status, out, err = self.run_fake(body + '\nemit({"type":"auto_retry_start"}); emit({"type":"auto_retry_end","success":False})')
        self.assertEqual((status, out, err), (1, b"", b"g: Pi retry did not complete\n"))

    def test_large_simultaneous_pipes_and_exact_non_tty_diagnostics(self):
        status, out, err = self.run_fake('''import threading
def diagnostics():
    for _ in range(512): os.write(2, b"diagnostic\\x00\\xff\\n" * 512)
thread = threading.Thread(target=diagnostics)
thread.start()
for _ in range(1024): emit({"type":"message_update","private":"x" * 4096})
thread.join()
final("done")
''')
        self.assertEqual(status, 0)
        self.assertEqual(out, b"done\n")
        self.assertEqual(err, b"diagnostic\x00\xff\n" * (512 * 512))
        self.assertNotIn(b"\x1b", err)

    def test_tail_after_exit_and_retained_pipe_idle_failure(self):
        # Forked fixture child retains Pi stdout after the direct child exits.
        self.fake('''final("old")
pid = os.fork()
if pid:
    os._exit(0)
os.setsid()
(root / "tail.pid").write_text(str(os.getpid()))
gate("tail")
# Ongoing post-exit data outlasts the idle limit without being truncated.
for _ in range(6):
    emit({"type":"future_event"})
    time.sleep(.4)
final("tail")
os._exit(0)
''')
        child, _ = self.start()
        self.ready("tail")
        self.assertEqual(select.select([child.stdout], [], [], 0)[0], [])
        wait_until(lambda: not alive(int((self.root / "pi.pid").read_text())))
        self.release("tail")
        out, err = child.communicate(timeout=6)
        self.assertEqual((child.returncode, out, err), (0, b"tail\n", b""))
        status, out, err = self.run_fake('''final("discard")
pid = os.fork()
if pid: os._exit(0)
os.setsid()
(root / "retained.pid").write_text(str(os.getpid()))
time.sleep(5)
''')
        self.assertEqual(status, 1)
        self.assertEqual(out, b"")
        self.assertIn(b"pipes stayed open", err)

    def test_cancellation_requests_cleanup_for_detached_helper(self):
        for incoming, expected in [(signal.SIGINT, signal.SIGTERM), (signal.SIGTERM, signal.SIGTERM), (signal.SIGHUP, signal.SIGHUP)]:
            with self.subTest(signal=incoming):
                for name in ["cancel.ready", "cancel", "received"]:
                    (self.root / name).unlink(missing_ok=True)
                self.fake('''helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"], start_new_session=True)
(root / "helper.pid").write_text(str(helper.pid))
def cleanup(sig, frame):
    (root / "received").write_text(str(sig))
    os.killpg(helper.pid, signal.SIGKILL)
    helper.wait(timeout=2)
    os.write(2, b"cleanup diagnostic\\n")
    sys.exit(128 + sig)
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGHUP, cleanup)
final("not published")
gate("cancel")
''')
                child, _ = self.start("-q")
                self.ready("cancel")
                pi_pid = int((self.root / "pi.pid").read_text())
                self.assertNotEqual(os.getpgid(pi_pid), os.getpgid(child.pid))
                os.killpg(child.pid, incoming)
                out, err = child.communicate(timeout=6)
                self.assertEqual(child.returncode, 128 + incoming)
                self.assertEqual(out, b"")
                self.assertEqual(err, b"cleanup diagnostic\n")
                self.assertEqual(int((self.root / "received").read_text()), expected)
                self.assertFalse(alive(int((self.root / "helper.pid").read_text())))
                self.assertFalse(alive(pi_pid))

    def test_stubborn_child_escalates_and_repeat_cancel_is_prompt(self):
        for repeat in [False, True]:
            for name in ["stubborn.ready", "stubborn", "ignored"]:
                (self.root / name).unlink(missing_ok=True)
            self.fake('''def ignore(sig, frame): (root / "ignored").touch()
signal.signal(signal.SIGTERM, ignore)
gate("stubborn")
''')
            child, _ = self.start()
            self.ready("stubborn")
            os.kill(child.pid, signal.SIGINT)
            wait_until(lambda: (self.root / "ignored").exists())
            start = time.monotonic()
            if repeat:
                os.kill(child.pid, signal.SIGINT)
            out, _ = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 130)
            self.assertEqual(out, b"")
            self.assertFalse(alive(int((self.root / "pi.pid").read_text())))
            if repeat:
                self.assertLess(time.monotonic() - start, 1.5)

    def test_broken_output_pipes_do_not_panic_or_orphan_pi(self):
        self.fake('final("done"); gate("broken")')
        child, _ = self.start()
        self.ready("broken")
        child.stdout.close()
        child.stdout = None
        self.release("broken")
        _, err = child.communicate(timeout=6)
        self.assertEqual(child.returncode, 1)
        self.assertNotIn(b"panicked", err)
        self.assertFalse(alive(int((self.root / "pi.pid").read_text())))
        self.fake('''def cleanup(sig, frame): sys.exit(143)
signal.signal(signal.SIGTERM, cleanup)
os.write(2, b"diagnostic")
time.sleep(10)
''')
        child, _ = self.start()
        child.stderr.close()
        child.stderr = None
        out, _ = child.communicate(timeout=6)
        self.assertNotEqual(child.returncode, 0)
        self.assertEqual(out, b"")
        self.assertFalse(alive(int((self.root / "pi.pid").read_text())))

    def blocked_launch(self, incoming, ignored=None):
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            capacity = 0
            while True:
                try: capacity += os.write(write_fd, b"x" * 4096)
                except BlockingIOError: break
            # Leave room only for diagnostic's initial "g: " write. Its arrival
            # proves the launch-error branch was reached; the remaining message
            # must block. No startup sleep or draining during cancellation.
            removed = os.read(read_fd, 4096)
            self.assertEqual(os.write(write_fd, b"x" * (len(removed) - 3)), len(removed) - 3)
            os.set_blocking(write_fd, True)
            child = subprocess.Popen([BINARY, "inspect"], env=self.env, cwd=self.root,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=write_fd, start_new_session=True,
                                     preexec_fn=(lambda: signal.signal(ignored, signal.SIG_IGN)) if ignored else None)
            self.children.append(child)
            def diagnostic_started():
                unread = struct.unpack("i", fcntl.ioctl(read_fd, termios.FIONREAD, struct.pack("i", 0)))[0]
                return unread == capacity
            wait_until(diagnostic_started)
            self.assertIsNone(child.poll())
            self.assertTrue(os.get_blocking(write_fd))
            if ignored:
                os.kill(child.pid, ignored)
                with self.assertRaises(subprocess.TimeoutExpired):
                    child.wait(timeout=.15)
            os.kill(child.pid, incoming)
            child.wait(timeout=2)
            self.assertEqual(child.returncode, -incoming)
            out, _ = child.communicate(timeout=2)
            self.assertEqual(out, b"")
            self.assertFalse((self.root / "pi.pid").exists())
            os.close(write_fd)
            write_fd = None
            data = bytearray()
            while len(data) < capacity:
                chunk = os.read(read_fd, capacity - len(data))
                if not chunk: break
                data.extend(chunk)
            self.assertEqual(data, b"x" * (capacity - 3) + b"g: ")
        finally:
            if write_fd is not None: os.close(write_fd)
            os.close(read_fd)

    def test_blocked_missing_and_nonexecutable_pi_diagnostics_are_cancellable(self):
        for installed, expected in [(False, b"could not find or start"), (True, b"permissions")]:
            if installed:
                self.fake('raise AssertionError("nonexecutable Pi must never run")')
                (self.root / "bin" / "pi").chmod(0o600)
            # Establish the branch-specific diagnostic in the same environment.
            child, _ = self.start()
            out, err = child.communicate(timeout=3)
            self.assertEqual(child.returncode, 1)
            self.assertEqual(out, b"")
            self.assertIn(expected, err)
            for incoming in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
                with self.subTest(installed=installed, signal=incoming):
                    self.blocked_launch(incoming)

    def test_early_diagnostic_restores_inherited_ignored_signal(self):
        self.blocked_launch(signal.SIGTERM, ignored=signal.SIGHUP)

    def test_full_unread_output_pipes_remain_cancellable(self):
        self.fake('''def cleanup(sig, frame):
    (root / "blocked-cleanup").touch()
    os._exit(143)
signal.signal(signal.SIGTERM, cleanup)
(root / "blocked.ready").touch()
while True: os.write(2, b"x" * 16384)
''')
        child, _ = self.start()
        self.ready("blocked")
        # Do not communicate/read: the inherited sink remains full during INT.
        wait_until(lambda: bool(select.select([child.stderr], [], [], 0)[0]))
        # A stable, nonempty unread byte count while the producer loops proves
        # downstream backpressure rather than relying only on startup timing.
        def stalled():
            before = fcntl.ioctl(child.stderr, termios.FIONREAD, struct.pack("i", 0))
            time.sleep(.1)
            after = fcntl.ioctl(child.stderr, termios.FIONREAD, struct.pack("i", 0))
            return before == after and struct.unpack("i", after)[0] > 0
        wait_until(stalled)
        os.kill(child.pid, signal.SIGINT)
        child.wait(timeout=4)
        self.assertEqual(child.returncode, 130)
        self.assertTrue((self.root / "blocked-cleanup").exists())
        self.assertFalse(alive(int((self.root / "pi.pid").read_text())))

        self.fake('final("x" * (3 * 1024 * 1024))')
        child, _ = self.start()
        wait_until(lambda: bool(select.select([child.stdout], [], [], 0)[0]))
        wait_until(lambda: not alive(int((self.root / "pi.pid").read_text())))
        os.kill(child.pid, signal.SIGINT)
        child.wait(timeout=4)
        self.assertEqual(child.returncode, 130)

        # Pre-fill an inherited stderr pipe. Only the final error diagnostic is
        # written by Genie, after Pi exits. Do not change shared descriptor flags.
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            while True:
                try: os.write(write_fd, b"x" * 4096)
                except BlockingIOError: break
            os.set_blocking(write_fd, True)
            self.fake('final("", "error")')
            child = subprocess.Popen([BINARY, "-q", "inspect"], env=self.env, cwd=self.root,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=write_fd, start_new_session=True)
            self.children.append(child)
            wait_until(lambda: (self.root / "pi.pid").exists() and not alive(int((self.root / "pi.pid").read_text())))
            self.assertTrue(os.get_blocking(write_fd))
            os.kill(child.pid, signal.SIGINT)
            child.wait(timeout=4)
            self.assertEqual(child.returncode, 130)
        finally:
            os.close(write_fd)
            os.close(read_fd)

    def test_pty_activity_concurrent_tools_resize_and_diagnostic_clear(self):
        self.fake('''gate("start")
for id in ["a", "b"]:
    emit({"type":"tool_execution_start","toolCallId":id,"toolName":"bash\\n\\x1b[31m" if id == "a" else "read", "args":"PRIVATE"})
gate("both")
emit({"type":"tool_execution_end","toolCallId":"a","isError":True})
gate("one")
emit({"type":"tool_execution_end","toolCallId":"b"})
gate("done")
os.write(2, b"Pi diagnostic\\n")
final("final")
''')
        child, master = self.start(tty=True, shared=True)
        data = self.read_pty(master, b"Starting Pi")
        self.ready("start")
        self.release("start")
        data += self.read_pty(master, b"Running bash___31m")
        self.release("both")
        data += self.read_pty(master, b"Running read")
        self.assertIn(b"1 completed calls", data)
        # Resize while a tool is active; inspect only newly rendered frames.
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 8, 0, 0))
        narrow = self.read_pty(master, b"\r\x1b[2K| Runni", timeout=3)
        frames = narrow.split(b"\r\x1b[2K")[1:]
        for frame in frames:
            self.assertLessEqual(len(frame), 7)
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        self.release("one")
        data += narrow + self.read_pty(master, b"2 completed calls")
        self.assertIn(b"Working", data)
        data += self.read_pty(master, b"1s | 2 completed calls")
        self.release("done")
        data += self.read_pty(master)
        child.wait(timeout=4)
        self.assertEqual(child.returncode, 0)
        self.assertNotIn(b"PRIVATE", data)
        self.assertNotIn(b"tool_execution", data)
        self.assertIn(b"\r\x1b[2KPi diagnostic\r\n", data)
        # A diagnostic can clear the last frame without a subsequent repaint.
        suffix = data[data.rfind(b"\r\x1b[2K"):]
        self.assertIn(suffix, [b"\r\x1b[2Kfinal\r\n", b"\r\x1b[2KPi diagnostic\r\nfinal\r\n"])

    def test_pty_quiet_dumb_failures_and_cancellation(self):
        for option, term in [("--quiet", "xterm"), ("-q", "xterm"), (None, "dumb")]:
            self.env["TERM"] = term
            self.fake('os.write(2, b"visible error\\n"); final("PRIVATE", "error")')
            child, master = self.start(*([option] if option else []), tty=True, shared=True)
            data = self.read_pty(master)
            child.wait(timeout=4)
            self.assertEqual(child.returncode, 1)
            self.assertNotIn(b"\x1b", data)
            self.assertIn(b"visible error", data)
            self.assertIn(b"g: Pi assistant ended with an error", data)
        self.env["TERM"] = "xterm"
        self.fake('gate("ptyerror"); final("PRIVATE", "error")')
        child, master = self.start(tty=True, shared=True)
        data = self.read_pty(master, b"Starting Pi")
        self.ready("ptyerror")
        self.release("ptyerror")
        data += self.read_pty(master)
        child.wait(timeout=4)
        self.assertEqual(child.returncode, 1)
        self.assertTrue(data.endswith(b"\r\x1b[2Kg: Pi assistant ended with an error\r\n"))
        self.assertNotIn(b"PRIVATE", data)
        self.fake('signal.signal(signal.SIGTERM, lambda s, f: sys.exit(143)); gate("ptycancel")')
        child, master = self.start(tty=True, shared=True)
        data = self.read_pty(master, b"Starting Pi")
        self.ready("ptycancel")
        os.kill(child.pid, signal.SIGINT)
        data += self.read_pty(master)
        child.wait(timeout=4)
        self.assertEqual(child.returncode, 130)
        self.assertTrue(data.endswith(b"\r\x1b[2K"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
