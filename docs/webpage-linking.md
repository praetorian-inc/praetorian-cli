# Webpage Source Linking

This feature allows you to link source code files and repositories to webpages in Chariot, helping you track where webpage content originates from.

## Overview

Webpage source linking creates associations between:
- Webpages discovered during security scanning
- Source code files (proofs, scan results, etc.)
- Source code repositories (GitHub, GitLab, etc.)

This helps security teams understand:
- Which repositories contain the code for discovered webpages
- Which scan result files are associated with specific webpages
- The relationship between discovered web assets and their source code

## CLI Usage

### Linking Sources to Webpages

To link a file or repository to a webpage:

```bash
# Link a file to a webpage
praetorian chariot link webpage-source "#webpage#https://example.com" "#file#proofs/scan.txt"

# Link a repository to a webpage
praetorian chariot link webpage-source "#webpage#https://example.com/login" "#repository#https://github.com/org/repo.git#repo.git"
```

### Unlinking Sources from Webpages

To remove a link between a source and a webpage:

```bash
# Unlink a file from a webpage
praetorian chariot unlink webpage-source "#webpage#https://example.com" "#file#proofs/scan.txt"

# Unlink a repository from a webpage
praetorian chariot unlink webpage-source "#webpage#https://example.com/login" "#repository#https://github.com/org/repo.git#repo.git"
```

## SDK Usage

The SDK provides methods for programmatically managing webpage source links:

```python
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain

# Initialize the SDK
chariot = Chariot(Keychain(account='chariot+example@praetorian.com'))

# Create a webpage first (if needed)
webpage_result = chariot.webpage.add('https://example.com')

# Link a file to a webpage
result = chariot.webpage.link_source(
    webpage_key='#webpage#https://example.com',
    entity_key='#file#proofs/scan.txt'
)
print(f"Linked source to webpage")

# Link a repository to a webpage
result = chariot.webpage.link_source(
    webpage_key='#webpage#https://example.com/app',
    entity_key='#repository#https://github.com/org/app.git#app.git'
)

# Unlink a source from a webpage
result = chariot.webpage.unlink_source(
    webpage_key='#webpage#https://example.com',
    entity_key='#file#proofs/scan.txt'
)

# Get webpage details (including linked artifacts)
webpage = chariot.webpage.get('#webpage#https://example.com')
if 'artifacts' in webpage:
    for artifact in webpage['artifacts']:
        print(f"Linked artifact: {artifact['key']} (Secret: {artifact.get('secret', 'N/A')})")

# List webpages with a filter
webpages, offset = chariot.webpage.list(filter='example.com')
for page in webpages:
    print(f"Webpage: {page['key']}")
```

## Key Format

### Webpage Keys
- Format: `#webpage#{url}`
- Example: `#webpage#https://example.com/login`

### File Keys
- Format: `#file#{path}`
- Example: `#file#proofs/vulnerability-scan.txt`

### Repository Keys
- Format: `#repository#{url}#{name}`
- Example: `#repository#https://github.com/org/repo.git#repo.git`

## Use Cases

1. **Source Code Tracking**: Link discovered webpages to their source repositories for easier remediation
2. **Scan Result Association**: Connect vulnerability scan results to the specific webpages they relate to
3. **Attack Surface Mapping**: Understand which repositories contribute to your external attack surface
4. **Compliance Tracking**: Document the relationship between code repositories and public-facing web assets

## Backend Structure

The webpage linking feature stores associations as `artifacts` on webpage entities. Each artifact contains:

- `key`: The entity key of the linked file or repository
- `secret`: Additional metadata (for repositories, contains secret/token information)

## Error Handling

The API will return appropriate error codes:
- `404`: When the webpage or entity (file/repository) is not found
- `400`: When the request format is invalid
- `200`: When the operation succeeds

## Notes

- Links are stored in the webpage's `artifacts` array as `WebpageCodeArtifact` objects
- Multiple sources can be linked to a single webpage
- Duplicate links are prevented automatically
- Both link and unlink operations are idempotent
- Repository entities may include secret information for authentication