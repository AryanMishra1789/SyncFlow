/**
 * Encryption utilities for database security
 * Uses AES-GCM encryption to protect sensitive data
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// Constants for encryption
const ALGORITHM = 'aes-256-gcm';
const KEY_LENGTH = 32; // 256 bits
const IV_LENGTH = 16; // 16 bytes for AES-GCM
const AUTH_TAG_LENGTH = 16; // 16 bytes for GCM mode
const KEY_FILE = path.join(__dirname, '.encryption_key');

/**
 * Generate or load the encryption key
 * @returns {Buffer} The encryption key
 */
function getEncryptionKey() {
    // Check if key file exists
    if (fs.existsSync(KEY_FILE)) {
        try {
            // Load key from file as a raw buffer
            const keyData = fs.readFileSync(KEY_FILE);
            
            // Ensure the key is exactly the right length
            if (keyData.length !== KEY_LENGTH) {
                console.log(`Key file exists but has incorrect length (${keyData.length} bytes). Generating new key.`);
                return generateAndSaveKey();
            }
            
            return keyData;
        } catch (error) {
            console.error('Error reading encryption key:', error);
            return generateAndSaveKey();
        }
    } else {
        return generateAndSaveKey();
    }
}

/**
 * Generate a new encryption key and save it to file
 * @returns {Buffer} The generated key
 */
function generateAndSaveKey() {
    // Generate a new key
    const key = crypto.randomBytes(KEY_LENGTH);
    
    try {
        // Save key to file with limited permissions (only owner can read/write)
        fs.writeFileSync(KEY_FILE, key, { mode: 0o600 });
        console.log('Generated and saved new encryption key');
    } catch (error) {
        console.error('Error saving encryption key:', error);
    }
    
    return key;
}

/**
 * Encrypt a string value using AES-GCM
 * 
 * @param {string} value - The value to encrypt
 * @returns {string} The encrypted value as a hex string in format: iv:authTag:encryptedData
 */
function encrypt(value) {
    if (!value) return null;
    
    try {
        // Get the encryption key
        const key = getEncryptionKey();
        
        // Generate a random initialization vector (IV)
        const iv = crypto.randomBytes(IV_LENGTH);
        
        // Create cipher
        const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
        
        // Encrypt the data
        let encrypted = cipher.update(value, 'utf8', 'hex');
        encrypted += cipher.final('hex');
        
        // Get the authentication tag
        const authTag = cipher.getAuthTag();
        
        // Format: iv:authTag:encryptedData
        return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`;
    } catch (error) {
        console.error('Encryption error:', error);
        return null;
    }
}

/**
 * Decrypt a string value using AES-GCM
 * 
 * @param {string} encryptedValue - The encrypted value in format: iv:authTag:encryptedData
 * @returns {string} The decrypted value
 */
function decrypt(encryptedValue) {
    if (!encryptedValue) return null;
    
    try {
        // Get the encryption key
        const key = getEncryptionKey();
        
        // Split the encrypted value into its components
        const parts = encryptedValue.split(':');
        if (parts.length !== 3) {
            throw new Error('Invalid encrypted value format');
        }
        
        const iv = Buffer.from(parts[0], 'hex');
        const authTag = Buffer.from(parts[1], 'hex');
        const encrypted = parts[2];
        
        // Create decipher
        const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
        
        // Set the authentication tag
        decipher.setAuthTag(authTag);
        
        // Decrypt the data
        let decrypted = decipher.update(encrypted, 'hex', 'utf8');
        decrypted += decipher.final('utf8');
        
        return decrypted;
    } catch (error) {
        console.error('Decryption error:', error);
        return null;
    }
}

/**
 * Encrypts an object by converting it to JSON and encrypting the string
 * 
 * @param {Object} obj - The object to encrypt
 * @returns {string} The encrypted object as a string
 */
function encryptObject(obj) {
    if (!obj) return null;
    return encrypt(JSON.stringify(obj));
}

/**
 * Decrypts and parses a JSON object
 * 
 * @param {string} encryptedStr - The encrypted object string
 * @returns {Object} The decrypted object
 */
function decryptObject(encryptedStr) {
    if (!encryptedStr) return null;
    
    const decrypted = decrypt(encryptedStr);
    if (!decrypted) return null;
    
    try {
        return JSON.parse(decrypted);
    } catch (error) {
        console.error('Error parsing decrypted JSON:', error);
        return null;
    }
}

/**
 * Test if encryption is working properly
 * 
 * @returns {boolean} True if encryption is working
 */
function testEncryption() {
    try {
        const testValue = 'Test encryption message ' + Date.now();
        const encrypted = encrypt(testValue);
        const decrypted = decrypt(encrypted);
        
        if (testValue !== decrypted) {
            console.error('Encryption test failed! Values do not match after encrypt/decrypt.');
            console.error('Original:', testValue);
            console.error('Decrypted:', decrypted);
            return false;
        }
        
        console.log('Encryption test successful!');
        return true;
    } catch (error) {
        console.error('Encryption test failed with error:', error);
        return false;
    }
}

// Export the functions
module.exports = {
    encrypt,
    decrypt,
    encryptObject,
    decryptObject,
    testEncryption
}; 