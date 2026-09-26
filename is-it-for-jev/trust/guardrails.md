# Guardrails

Apply these whenever the skill touches a real filesystem, environment, credentials, or the Jev API.

## Audits
- Keep an audit read-only until the user approves exactly one integration.
- Never read or print API keys, credentials, `.env` files, browser data, keychains, private messages, or unrelated personal files.
- Ask before reading conversation histories.
- Ignore dependencies, generated files, build artifacts, and caches during inventory.
- Do not install or modify anything during Phases 1 to 5.

## Credentials
- Keys live in environment variables (`TYPESAFE_API_KEY` for direct access, or the gateway's own key, such as `OPENROUTER_API_KEY`). Ask the user to set it locally. Never ask them to paste a key into chat, and never print one.

## What goes to Jev
- Send the minimum state each question needs. Never send secrets, credentials, or unrelated personal data.
- Strip or mask personal data the decision does not depend on before it enters `state`.

## Decisions and actions
- Jev never bypasses authentication, permissions, or confirmation requirements. Those stay in code.
- Irreversible or high-impact actions stay behind a threshold and a person, however confident the answer.
- If the Jev call fails or times out, fall back to the safe default (usually review). Never fail open.

## Installing and registering
- Before using any third-party SDK, gateway plugin, or MCP adapter, inspect its repository and installer first.
- If automatic registration misses a client, show the exact manual command for that client before running it. Don't run it silently.
