# Agent instructions

Read [README.md](README.md) and [the setup workflow](docs/agent-setup.md) before
preparing an owner's home. This is the Samsung Tizen project. CleanYourTV's
Android commands and `PROMPT.md` do not apply here.

## Set up an owner's home

- Discover before asking. Collect HDMI sources and installed TV apps through
  the read-only discovery script where Samsung Web Inspector is available.
  Include disconnected ports; a sleeping device can appear disconnected.
- Use saved source names and exact installed application IDs. Do not copy the
  example owner's destinations or infer a device from its HDMI number.
- This Q70T's public API omits saved HDMI names. Use an existing native-name
  export or inspect the TV's Sources screen when accessible. Do not build a
  root, private-shell or injection-based collector to fill the gap.
- Keep generic labels, duplicate names and inaccessible data unresolved. Ask
  one focused question only when the evidence cannot distinguish the targets.
  A blanket request for the owner to assign every port is not the setup flow.
- Find matching logos, store them locally, and record their source and license
  information. Prefer the existing verified assets or official brand assets.
  Keep a missing logo unresolved. The TV must not fetch logos from the network.
- Generate the inventory, plan, home configuration and staged app under
  `.local/`. Resolve or explicitly exclude every unresolved destination before
  packaging. Preview the owner's staged app, then verify the actual TV actions.
- Keep Samsung Home available. Installing the dashboard does not authorize
  changing the physical Home route or startup settings. Follow
  [Home routing and recovery](docs/home-route.md) for that separate task.

## Device and repository limits

- Use owner-controlled Samsung signing tools. Keep certificates, private keys,
  DUIDs, addresses, exports, packages and unredacted TV captures out of Git.
- Do not disable or uninstall Samsung packages, edit vendor services, bypass
  signature policy, or add a resident Home watcher. No reversible Samsung
  package-disable procedure is established here.
- Never uninstall an active Home-route carrier. Keep its tested signed restore
  package and verify loaded rules as well as stored registry rows.
- Keep the app offline. No network permission, remote assets, telemetry,
  background services or polling loops.
- Report only observed results with the model and firmware. Browser previews
  do not prove HDMI switching, app launches, physical Home or automatic startup.
- Keep Samsung implementation in this repository. An upstream CleanYourTV
  contribution belongs in its showcase workflow; do not change Android safety
  rules or add Samsung commands to its `PROMPT.md`.
- Use plain text without em dashes. Update `CHANGELOG.md` for finished new work.

For code changes, run the relevant Node and Python tests documented in the
README. Do not run a frontend polish pass for an ordinary installation. Keep
owner-specific generated files private instead of editing the tracked example.
