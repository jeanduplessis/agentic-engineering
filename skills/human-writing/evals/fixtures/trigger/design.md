# Request worker

The worker retries a failed request at most twice. After the second retry fails, it returns an error to the caller.
