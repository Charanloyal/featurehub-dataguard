# Security Policy

## Reporting Security Issues

Please do not report security vulnerabilities through public GitHub issues.
Instead, report security concerns directly to the platform security team.

## Credentials & Secret Handling

- Never commit credentials, passwords, database URLs with embedded secrets, or API keys to the repository.
- Use `.env` populated from `.env.example` for local credentials.
- CI workflows store production tokens and keys strictly inside GitHub Secrets.
