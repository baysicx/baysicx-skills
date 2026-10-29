# Packaging Contracts

Apply this reference when changing Python distribution metadata, build
configuration, wheel or sdist contents, package data, typing markers, entry
points, or behavior after installation. Follow the repository's chosen layout,
frontend, backend, and installer.

## Identify the distribution contract

- Distinguish the distribution name, import package, module entry point, console
  script, and `python -m` route. Similar names do not prove that these surfaces
  resolve to the same implementation.
- Identify the authoritative packaging configuration, build frontend and
  backend, dependency or lock policy, target runtimes, and any generated inputs.
- Resolve duplicate, inherited, or obsolete metadata before editing. A parseable
  configuration file may not be the configuration used by the real build.
- After metadata changes, run the repository-native schema or metadata
  validation; parsing TOML alone does not establish a valid distribution.

## Inspect the real artifacts

- Build each artifact type the repository declares, such as a wheel or sdist,
  using its native command and supported environment.
- Inspect artifact paths and metadata for expected modules, forbidden files,
  package data, dependency declarations, entry points, and `py.typed` when typed
  package support is promised.
- Install the built artifact in an isolated environment outside the source tree.
  Verify public imports, console scripts, supported `python -m` routes, and
  resource access from that installation so the checkout cannot shadow a broken
  artifact.
- For a packaging-configuration migration, build artifacts before and after the
  migration and compare their relevant contents and metadata. Remove the old
  configuration only after the intended equivalence or intentional differences
  are established.

## Respect platform boundaries

- Validate native extensions separately for each declared interpreter, ABI,
  operating system, and architecture that the available environment can
  represent. A successful local build does not prove another target.
- Distinguish building, installing, importing, and executing; success at one
  stage does not establish the next.
- Packaging validation ends with local artifacts and their installed behavior.
  Do not publish, upload, tag, change release channels, or modify a release
  process unless the user separately authorizes that action.
