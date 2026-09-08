"""Synthetic review fixture: a tiny Markdown-like link visitor, not production code."""

from html import escape
import re
import unittest


def parse(source):
    match = re.fullmatch(r"\[([^]]+)\]\((.*)\)", source)
    if match:
        return {"kind": "link", "text": match[1], "url": match[2]}
    if source.startswith("<"):
        return {"kind": "raw_html", "value": source}
    return {"kind": "text", "value": source}


def visit_link(node):
    url = node["url"]
    if url.lower().startswith("javascript:"):
        url = "#"
    return f'<a href="{escape(url, quote=True)}">{escape(node["text"])}</a>'


def render(source):
    node = parse(source)
    if node["kind"] == "link":
        return visit_link(node)
    if node["kind"] == "raw_html":
        return node["value"]
    return escape(node["value"])


class VisitorTests(unittest.TestCase):
    def test_ordinary_markdown_link(self):
        self.assertEqual(render("[safe](https://example.invalid)"),
                         '<a href="https://example.invalid">safe</a>')

    def test_javascript_markdown_link_is_neutralized(self):
        self.assertEqual(render("[unsafe](javascript:alert(1))"),
                         '<a href="#">unsafe</a>')


if __name__ == "__main__":
    unittest.main()
