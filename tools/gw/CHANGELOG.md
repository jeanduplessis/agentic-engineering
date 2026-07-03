# Changelog

## 1.1.0

- Added `optional: true` for `copy` and `symlink` post-create hooks.
- Missing optional hook sources are skipped instead of failing the post-create hook chain.
- Copy and symlink hooks remain strict by default, so existing configurations still warn on missing sources unless they opt in.
