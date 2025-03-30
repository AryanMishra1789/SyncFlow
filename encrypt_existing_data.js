/**
 * Directly encrypt existing database records
 * Run this script with: node encrypt_existing_data.js
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const crypto = require('crypto');
const fs = require('fs');

// Constants for encryption
const ALGORITHM = 'aes-256-gcm';
const KEY_LENGTH = 32; // 256 bits
const IV_LENGTH = 16; // 16 bytes for AES-GCM
const AUTH_TAG_LENGTH = 16; // 16 bytes for GCM mode
const KEY_FILE = path.join(__dirname, '.encryption_key');

// Load or create encryption key
function getEncryptionKey() {
    if (fs.existsSync(KEY_FILE)) {
        try {
            const keyData = fs.readFileSync(KEY_FILE);
            if (keyData.length !== KEY_LENGTH) {
                console.log(`Key file exists but has incorrect length. Generating new key.`);
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

function generateAndSaveKey() {
    const key = crypto.randomBytes(KEY_LENGTH);
    try {
        fs.writeFileSync(KEY_FILE, key, { mode: 0o600 });
        console.log('Generated and saved new encryption key');
    } catch (error) {
        console.error('Error saving encryption key:', error);
    }
    return key;
}

// Encrypt a value
function encrypt(value) {
    if (!value) return null;
    
    try {
        const key = getEncryptionKey();
        const iv = crypto.randomBytes(IV_LENGTH);
        const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
        
        let encrypted = cipher.update(value, 'utf8', 'hex');
        encrypted += cipher.final('hex');
        
        const authTag = cipher.getAuthTag();
        
        // Format: iv:authTag:encryptedData
        return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`;
    } catch (error) {
        console.error('Encryption error:', error);
        return null;
    }
}

// Check if a value is already encrypted
function isEncrypted(value) {
    if (!value || typeof value !== 'string') return false;
    
    const parts = value.split(':');
    if (parts.length !== 3) return false;
    
    return (
        parts[0].length === 32 && 
        /^[0-9a-f]+$/i.test(parts[0]) &&
        parts[1].length === 32 && 
        /^[0-9a-f]+$/i.test(parts[1]) &&
        parts[2].length > 0
    );
}

// Process a database
async function encryptDatabase(dbPath, tables) {
    return new Promise((resolve, reject) => {
        console.log(`Opening database: ${dbPath}`);
        
        const db = new sqlite3.Database(dbPath, async (err) => {
            if (err) {
                console.error(`Error opening database ${dbPath}:`, err);
                return reject(err);
            }
            
            try {
                console.log(`Processing ${tables.length} tables in ${dbPath}`);
                
                for (const table of tables) {
                    await encryptTable(db, table.name, table.columns);
                }
                
                db.close();
                console.log(`✅ Completed encrypting ${dbPath}`);
                resolve();
            } catch (error) {
                console.error(`Error processing ${dbPath}:`, error);
                db.close();
                reject(error);
            }
        });
    });
}

// Process a table
async function encryptTable(db, tableName, columns) {
    return new Promise((resolve, reject) => {
        console.log(`\nEncrypting table: ${tableName}`);
        console.log(`Fields to encrypt: ${columns.join(', ')}`);
        
        // First, check if table exists
        db.get(`SELECT name FROM sqlite_master WHERE type='table' AND name=?`, [tableName], (err, table) => {
            if (err) {
                console.error(`Error checking table ${tableName}:`, err);
                return reject(err);
            }
            
            if (!table) {
                console.log(`⚠️ Table ${tableName} does not exist, skipping.`);
                return resolve();
            }
            
            // Get all records from the table
            db.all(`SELECT * FROM ${tableName}`, [], async (err, rows) => {
                if (err) {
                    console.error(`Error reading from ${tableName}:`, err);
                    return reject(err);
                }
                
                console.log(`Found ${rows.length} records in ${tableName}`);
                let encryptedCount = 0;
                
                // Process each row
                for (const row of rows) {
                    try {
                        const updates = [];
                        const params = [];
                        
                        // Check each column that should be encrypted
                        for (const col of columns) {
                            // Skip if column doesn't exist in this row
                            if (row[col] === undefined) continue;
                            
                            // Skip if already encrypted or null
                            if (!row[col] || isEncrypted(row[col])) continue;
                            
                            // Encrypt the column
                            const encrypted = encrypt(String(row[col]));
                            if (encrypted) {
                                updates.push(`${col} = ?`);
                                params.push(encrypted);
                            }
                        }
                        
                        // If we have updates to make
                        if (updates.length > 0) {
                            params.push(row.id); // For WHERE clause
                            
                            await new Promise((resolveUpdate, rejectUpdate) => {
                                const updateSql = `UPDATE ${tableName} SET ${updates.join(', ')} WHERE id = ?`;
                                db.run(updateSql, params, function(err) {
                                    if (err) {
                                        console.error(`Error updating row ${row.id}:`, err);
                                        return rejectUpdate(err);
                                    }
                                    
                                    encryptedCount++;
                                    resolveUpdate();
                                });
                            });
                        }
                    } catch (error) {
                        console.error(`Error processing row ${row.id}:`, error);
                        // Continue with other rows
                    }
                }
                
                console.log(`✅ Encrypted ${encryptedCount} rows in ${tableName}`);
                resolve();
            });
        });
    });
}

// Main function
async function main() {
    try {
        const databases = [
            {
                path: path.join(__dirname, 'emails2.db'),
                tables: [
                    { name: 'emails', columns: ['subject', 'body', 'sender', 'receiver', 'content'] },
                    { name: 'threads', columns: ['subject', 'snippet'] },
                    { name: 'messages', columns: ['subject', 'body', 'from', 'to', 'cc', 'bcc'] }
                ]
            },
            {
                path: path.join(__dirname, 'history.db'),
                tables: [
                    { name: 'history', columns: ['url', 'website_name', 'domain'] },
                    { name: 'recommendations', columns: ['url', 'title', 'description'] }
                ]
            },
            {
                path: path.join(__dirname, 'email_analysis.db'),
                tables: [
                    { name: 'email_styles', columns: ['style', 'formality', 'tone'] },
                    { name: 'enhanced_email_styles', columns: ['style_data'] },
                    { name: 'contacts', columns: ['email', 'name', 'frequency_data'] }
                ]
            }
        ];
        
        console.log("🔐 Starting direct encryption of existing database records...");
        
        // Process each database
        for (const db of databases) {
            await encryptDatabase(db.path, db.tables);
        }
        
        console.log("\n✅ All databases processed successfully");
        console.log("Your existing data is now encrypted! 🔒");
    } catch (error) {
        console.error("❌ Error during encryption process:", error);
    }
}

// Run the script
main(); 