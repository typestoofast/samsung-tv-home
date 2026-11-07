# Physical Home on the Q70T

The owner confirmed on 6 November 2026 that a short press of Samsung Home opens
Four without Samsung's bar. The test device is QN65Q70TAFXZC, Tizen 5.5.0,
firmware T-NKMAKUC-2743.0. Other models, firmware updates, cold-boot persistence,
and the Apple TV remote's Home button are not verified.

The mechanism is an undocumented Samsung manifest extension. A signed native
companion replaces the existing `com.samsung.tv.csfs` short-Home target with
`org.four.home.route`. Its one-shot .NET program launches Four and exits. The
original Source rule and separate long-Home rule remain unchanged. Samsung Home
stays installed, and Four has an explicit Samsung Home button.

A parallel rule with `override="true"` launched Samsung's bar before Four.
This TV also parsed only the first `app-context` block in a package. The builder
therefore emits exactly one context in each package.

## Prerequisites and limits

This is a source-buildable research tool, not a general Samsung installer.
It does not collect a baseline or connect to the TV. Installation requires:

- A working Four installation with checked HDMI/app shortcuts.
- Samsung Tizen Studio and your own TV signing profile, with the TV's DUID added
  privately through Samsung Certificate Manager.
- .NET SDK 8 to compile the small companion against `netcoreapp3.0`, the runtime
  used by this TV. This old target is a device constraint, not a current .NET
  recommendation. No runtime is installed on the TV by this project.
- An independently captured original routing snapshot and a way to inspect fresh
  snapshots and the running key-manager configuration. Normal retail SDB shell
  access may not provide this. This repository does not include a supported
  collector. If you cannot capture and verify the baseline, stop at the dashboard.

The recorded development session used undocumented developer access for native
inspection and setting changes. Root was not used. Do not treat this as a public
Samsung launcher API or fabricate a baseline to satisfy the builder.

Keep the original snapshot, recovery packages, certificates and all device
identifiers private. Build output goes under `.local/` or `dist/`, both ignored.

## Snapshot format

A private JSON object has `model`, `firmware`, `tizen`, and `tables`. The tables
contain every row in `managed_app`, `key_filter`, and `task_filter`, in their
schema column order, with SQL NULL represented as JSON null. There are no row IDs.
This device's untouched baseline had 28 managed apps, 70 key rules and no task
rules. The builder checks the exact Samsung Home and Source entries, and refuses
an existing Four registration in the original snapshot.

Do not import the snapshot into the TV. It is comparison evidence only. No SQL
write is needed: the TV package manager processes the signed manifests.

## Build and recovery sequence

```sh
python3 tools/home-route.py build \
  --baseline .local/original-routing.json --out .local/home-packages
```

This creates unsigned `register.tpk`, `apply.tpk`, and `restore.tpk` from source.
Inspect the generated manifests, then sign all three with Tizen CLI. For example,
using your own profile and an absolute output path:

```sh
tizen package -t tpk -s YOUR_PROFILE \
  -o /absolute/private/path/signed-restore -- .local/home-packages/restore.tpk
```

Before any stock-rule change, save the signed restore package outside the checkout.
Use the official Tizen installer for each package. The staged sequence is:

1. Install **register** once. It creates an inert managed-app entry for the
   companion, with no key rules. Compare the complete registry with the original.
2. Install **restore** and verify the complete original registry, apart from that
   one additional inert managed-app entry.
3. Install **apply**. Verify that exactly the existing short-Home target and its
   argument changed, and no other row changed. There must be no parallel Four rule.
4. Install **restore** again and verify exact logical restoration. Test stock Home.
5. Reapply, verify both stored rules and the running manager's loaded rules, then
   press the physical Home button from HDMI and a streaming app. Verify Samsung
   Home through Four's footer as well. Stop and restore if behavior differs.

The `check` command compares every row, including duplicates:

```sh
python3 tools/home-route.py check --baseline .local/original-routing.json \
  --current .local/current-routing.json --state apply
```

Use `--state restore` or `--state register` for the other stages. Stored rows
alone do not prove physical behavior. On this firmware, a package-triggered
manager reload sometimes preceded the new manifest's parsing. A same-package
reinstall then loaded the correct rule. Confirm the loaded target in the manager
logs before testing; do not repeatedly reinstall or restart services blindly.

The tested versions are register 0.2.1, apply 0.2.2, restore 0.2.3. Reinstalling
the lower apply version after restore worked on this TV. Do not assume other
firmware permits it, or overwrite a newer companion from another installation.

**Never uninstall the carrier.** Removing it can remove the Samsung context it
registered. Restore explicitly with the signed restore package and leave the
inert carrier installed. An empty own-app context, the register package, or a
package with two context blocks is not a stock-rule rollback. Keep recovery
material after turning Developer Mode off.

## References

The existing-rule approach was researched against
[samsung-tizen-home-remap](https://github.com/chutovkatest/samsung-tizen-home-remap)
and [samsung-tizen-homekey](https://github.com/gtalusan/samsung-tizen-homekey).
The companion and builder here are source implementations for the independently
captured Q70T baseline. No vendor binaries, original manifest dumps or signing
material are distributed.
