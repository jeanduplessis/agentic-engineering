# Custom Kilo provider for Pi

A local variant of the Kilo-maintained Pi provider. It keeps the provider and
login behavior from Kilo while leaving footer rendering to the local
`custom-footer` extension.

## Changes from the upstream provider

- Does not call `setFooter()`.
- Publishes the current balance through the `kilo-credits` status key for
  `custom-footer` to read.
- Formats the balance as plain credit text such as `$573.60`, without an emoji
  prefix.
- Marks a missing off/none thinking variant as unsupported so Pi does not send
  `reasoning_effort: none` to models such as `kilo-internal/galaxy`.
- Exposes `xhigh` and `max` as separate thinking levels when the gateway advertises
  them, preserving each variant's provider effort value.

## Installation

Pi auto-discovers the provider from `extensions/kilo-pi-provider`, so no
`settings.json` entry is required.

## Usage

Start Pi as usual. Free Kilo Gateway models are available without signing in.
To access the full model catalog, sign in with your Kilo account:

```text
/login kilo
```

This opens a browser for device authorization. If the account belongs to
organizations, Pi lets you choose which Kilo account to use.

You can also set `KILO_API_KEY` directly. Set `KILO_ORG_ID` or
`KILOCODE_ORGANIZATION_ID` to select an organization account.

## License and attribution

This provider is based on the Kilo-maintained derivative of
[mrexodia/kilo-pi-provider](https://github.com/mrexodia/kilo-pi-provider). The
original source and Kilo modifications are distributed under the [Boost
Software License 1.0](./LICENSE).
