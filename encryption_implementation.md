# Database Encryption Implementation

## Overview

This document describes the implementation of AES-GCM encryption for database storage in the application. The following files have been created or modified to implement the encryption system:

1. `encryption_utils.js` - Core encryption/decryption utilities
2. `encrypted_db.js` - SQLite database wrapper with encryption support
3. `db_manager.js` - Database management with encryption configuration
4. Modified database access in `main.js`

## Encryption System

### Encryption Algorithm

The system uses the AES-GCM (Advanced Encryption Standard with Galois/Counter Mode) encryption algorithm, which provides both confidentiality and authenticity:

- **Key Length**: 256 bits
- **IV Length**: 16 bytes (random for each encryption)
- **Auth Tag Length**: 16 bytes (for integrity verification)

### Key Management

- A random encryption key is generated and stored in a key file (`encryption_key.dat`) in the application directory
- The key file permissions are restricted to minimize access
- The key is loaded from this file each time encryption/decryption is needed

## Database Architecture

### Encrypted Databases

The following databases are encrypted:
- `history.db` - Browsing history and recommendations
- `emails2.db` - Email storage
- `email_analysis.db` - Email analysis results
- `activity.db` - User activity tracking

### Encrypted Columns Configuration

Each database has specific columns designated for encryption in the `DB_CONFIG` object in `db_manager.js`. For example:

```javascript
'activity.db': {
    encryptedColumns: {
        activities: ['description', 'metadata']
    }
}
```

## Implementation Details

### `encryption_utils.js`

- `getEncryptionKey()` - Creates or loads the encryption key
- `encrypt(value)` - Encrypts a string value, returning "iv:authTag:encryptedData"
- `decrypt(encryptedValue)` - Decrypts the encrypted value
- `encryptObject(obj)` - Encrypts a JSON object
- `decryptObject(encryptedObj)` - Decrypts a JSON object
- `testEncryption()` - Tests the encryption/decryption system

### `encrypted_db.js`

A SQLite database wrapper that provides:
- Transparent encryption/decryption of data
- Promise-based API
- Transaction support
- Methods for inserting, updating, and querying with automatic encryption/decryption

### `db_manager.js`

Central manager for all database operations:
- Database connection pooling
- Configuration of which columns should be encrypted
- High-level API for inserting, updating, and querying
- Table creation and schema management

## Usage Examples

### Inserting Data

```javascript
await dbManager.insert('activity.db', 'activities', {
    type: 'email',
    description: 'Email Generation', // Will be encrypted
    timestamp: new Date().toISOString(),
    metadata: JSON.stringify({ subject: 'Test' }) // Will be encrypted
});
```

### Querying Data

```javascript
const activities = await dbManager.query(
    'activity.db',
    'SELECT * FROM activities ORDER BY timestamp DESC LIMIT ?',
    [10],
    'activities' // Table name for decryption configuration
);
```

## Security Considerations

1. The encryption key is stored locally, so physical security of the device is important
2. Memory protection is limited by JavaScript runtime capabilities
3. The system focuses on data-at-rest protection, not in-transit
4. Python scripts still access the raw database files directly

## Future Improvements

1. Add key rotation capabilities
2. Implement secure key storage using OS-specific secure storage
3. Add Python-side encryption for full coverage
4. Enable configurable encryption levels per application 