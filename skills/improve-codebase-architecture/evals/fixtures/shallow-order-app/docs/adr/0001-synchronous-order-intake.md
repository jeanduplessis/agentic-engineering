# Keep Order intake synchronous

Order intake returns a confirmed or rejected Order in the request path because support staff need immediate feedback during phone orders. Revisit only if checkout latency or partner timeouts become the dominant source of failures.
