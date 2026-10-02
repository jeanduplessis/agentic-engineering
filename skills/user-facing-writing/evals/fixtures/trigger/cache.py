def evict_oldest(entries):
    """Remove and return the oldest entry (stored at index zero)."""
    return entries.pop()
