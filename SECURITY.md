# Security and evidence handling

## Local viewer

The viewer is designed for local analysis and binds to `127.0.0.1` by default.
It has no authentication layer and must not be exposed to an untrusted network.
Do not use `--host 0.0.0.0` with sensitive evidence unless access is protected
by controls outside this application.

The interface uses no external scripts, fonts, analytics, APIs, or content
delivery networks. Responses disable browser caching and include restrictive
content-security, framing, content-type, and referrer headers.

## Investigator workstation

Use a dedicated browser profile without extensions when reviewing sensitive
content. Consider browser crash reporting, clipboard managers, screenshots,
swap, backups, and shell history when applying the laboratory's evidence
handling policy.

## Reporting issues

Do not include evidence content, credentials, personal data, or restricted
paths in a public issue. Follow the disclosure channel associated with the
paper artifact or repository.
