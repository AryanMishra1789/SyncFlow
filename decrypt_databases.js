/**
 * Database Decryption Script
 * This script decrypts data in activity.db and history.db 
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

// Load encryption key
function getEncryptionKey() {
    if (fs.existsSync(KEY_FILE)) {
        try {
            const keyData = fs.readFileSync(KEY_FILE);
            return keyData;
        } catch (error) {
            console.error('Error reading encryption key:', error);
            throw new Error('Cannot read encryption key');
        }
    } else {
        throw new Error('Encryption key not found');
    }
}

// Decrypt a value
function decrypt(encryptedValue) {
    if (!encryptedValue) return null;
    
    try {
        // Split the string into parts: iv:authTag:encryptedData
        const parts = encryptedValue.split(':');
        if (parts.length !== 3) {
            return encryptedValue; // Not encrypted in our format
        }
        
        const iv = Buffer.from(parts[0], 'hex');
        const authTag = Buffer.from(parts[1], 'hex');
        const encryptedData = Buffer.from(parts[2], 'hex');
        
        const key = getEncryptionKey();
        const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
        decipher.setAuthTag(authTag);
        
        let decrypted = decipher.update(encryptedData, 'hex', 'utf8');
        decrypted += decipher.final('utf8');
        
        return decrypted;
    } catch (error) {
        console.error('Decryption error:', error);
        return encryptedValue; // Return original if decryption fails
    }
}

// Check if a value is encrypted
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

// Make the database writeable
function makeWriteable(dbPath) {
    try {
        fs.chmodSync(dbPath, 0o644);
        return true;
    } catch (error) {
        console.error(`Error making database writeable: ${dbPath}`, error);
        return false;
    }
}

// Make the database read-only
function makeReadOnly(dbPath) {
    try {
        fs.chmodSync(dbPath, 0o444);
        return true;
    } catch (error) {
        console.error(`Error making database read-only: ${dbPath}`, error);
        return false;
    }
}

// Database configurations - mapping encrypted columns for each table
const dbConfigs = {
    'history.db': {
        'history': ['url', 'website_name', 'domain', 'title'],
        'recommendations': ['url', 'title', 'description']
    },
    'activity.db': {
        'activities': ['description', 'metadata']
    }
};

// Decrypt a database
async function decryptDatabase(dbPath, config) {
    return new Promise(async (resolve, reject) => {
        console.log(`\n📁 Decrypting database: ${dbPath}`);
        
        // Check if the file exists
        if (!fs.existsSync(dbPath)) {
            console.log(`❌ Database file not found: ${dbPath}`);
            return resolve();
        }
        
        // Make the database writeable
        if (!makeWriteable(dbPath)) {
            console.log(`❌ Cannot make database writeable: ${dbPath}`);
            return resolve();
        }
        
        // Create a backup
        const backupPath = `${dbPath}.bak.${Date.now()}`;
        try {
            fs.copyFileSync(dbPath, backupPath);
            console.log(`Created backup at ${backupPath}`);
        } catch (error) {
            console.error(`Error creating backup: ${error.message}`);
            return resolve();
        }
        
        const db = new sqlite3.Database(dbPath, async (err) => {
            if (err) {
                console.error(`Error opening database ${dbPath}:`, err);
                return reject(err);
            }
            
            try {
                // Get all tables
                const tables = await new Promise((resolve, reject) => {
                    db.all("SELECT name FROM sqlite_master WHERE type='table'", (err, rows) => {
                        if (err) reject(err);
                        else resolve(rows.map(row => row.name));
                    });
                });
                
                console.log(`Found tables: ${tables.join(', ')}`);
                
                // Process each table in the configuration
                for (const [tableName, encryptedColumns] of Object.entries(config)) {
                    if (!tables.includes(tableName)) {
                        console.log(`⚠️ Table ${tableName} does not exist in ${dbPath}`);
                        continue;
                    }
                    
                    // Get columns for this table
                    const pragmaResults = await new Promise((resolve, reject) => {
                        db.all(`PRAGMA table_info(${tableName})`, (err, rows) => {
                            if (err) reject(err);
                            else resolve(rows);
                        });
                    });
                    
                    const actualColumns = pragmaResults.map(row => row.name);
                    console.log(`\n🔍 Table ${tableName} columns: ${actualColumns.join(', ')}`);
                    
                    // Filter encrypted columns that actually exist
                    const columnsToDecrypt = encryptedColumns.filter(col => actualColumns.includes(col));
                    console.log(`🔓 Columns to decrypt: ${columnsToDecrypt.join(', ')}`);
                    
                    if (columnsToDecrypt.length === 0) {
                        console.log(`⚠️ No valid columns to decrypt in table ${tableName}`);
                        continue;
                    }
                    
                    // Get all rows from the table
                    const rows = await new Promise((resolve, reject) => {
                        db.all(`SELECT * FROM ${tableName}`, (err, rows) => {
                            if (err) reject(err);
                            else resolve(rows || []);
                        });
                    });
                    
                    console.log(`Processing ${rows.length} rows in ${tableName}...`);
                    let decryptedCount = 0;
                    
                    // Process each row
                    for (const row of rows) {
                        const updates = [];
                        const params = [];
                        
                        // Check each column that might be encrypted
                        for (const col of columnsToDecrypt) {
                            // Skip if column value is null or undefined
                            if (row[col] === null || row[col] === undefined) continue;
                            
                            // Skip if not encrypted
                            if (!isEncrypted(row[col])) {
                                continue;
                            }
                            
                            // Decrypt the column
                            const decrypted = decrypt(row[col]);
                            if (decrypted && decrypted !== row[col]) {
                                updates.push(`${col} = ?`);
                                params.push(decrypted);
                            }
                        }
                        
                        // If we have updates to make
                        if (updates.length > 0) {
                            // Add the ID for the WHERE clause
                            params.push(row.id); 
                            
                            await new Promise((resolveUpdate, rejectUpdate) => {
                                const updateSql = `UPDATE ${tableName} SET ${updates.join(', ')} WHERE id = ?`;
                                db.run(updateSql, params, function(err) {
                                    if (err) {
                                        console.error(`Error updating row ${row.id}:`, err);
                                        return rejectUpdate(err);
                                    }
                                    
                                    decryptedCount++;
                                    resolveUpdate();
                                });
                            });
                        }
                    }
                    
                    console.log(`✅ Decrypted ${decryptedCount} rows in ${tableName}`);
                }
                
                // Close the database
                db.close();
                
                console.log(`✅ Completed decrypting ${dbPath}`);
                resolve();
            } catch (error) {
                console.error(`Error processing ${dbPath}:`, error);
                db.close();
                reject(error);
            }
        });
    });
}

// Verify decryption
async function verifyDecryption(dbPath, config) {
    return new Promise(async (resolve, reject) => {
        console.log(`\n🔍 Verifying decryption in: ${dbPath}`);
        
        if (!fs.existsSync(dbPath)) {
            console.log(`❌ Database file not found: ${dbPath}`);
            return resolve();
        }
        
        const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY, async (err) => {
            if (err) {
                console.error(`Error opening database ${dbPath}:`, err);
                return reject(err);
            }
            
            try {
                // Check each table
                for (const [tableName, columns] of Object.entries(config)) {
                    // Check if table exists
                    const tableExists = await new Promise((resolve) => {
                        db.get(`SELECT name FROM sqlite_master WHERE type='table' AND name=?`, [tableName], (err, row) => {
                            resolve(!!row);
                        });
                    });
                    
                    if (!tableExists) {
                        console.log(`⚠️ Table ${tableName} does not exist in ${dbPath}`);
                        continue;
                    }
                    
                    // Get a few rows
                    const rows = await new Promise((resolve, reject) => {
                        db.all(`SELECT * FROM ${tableName} LIMIT 5`, (err, rows) => {
                            if (err) reject(err);
                            else resolve(rows || []);
                        });
                    });
                    
                    if (rows.length === 0) {
                        console.log(`⚠️ No data in table ${tableName}`);
                        continue;
                    }
                    
                    console.log(`\nVerifying table ${tableName} decryption:`);
                    
                    let allDecrypted = true;
                    
                    // Check each row
                    for (let i = 0; i < rows.length; i++) {
                        const row = rows[i];
                        
                        // Check each column
                        for (const col of columns) {
                            if (!(col in row)) {
                                continue;
                            }
                            
                            const value = row[col];
                            if (value === null || value === undefined) {
                                continue;
                            }
                            
                            if (isEncrypted(value)) {
                                console.log(`  - ❌ Column ${col} in row ${i+1} is still encrypted`);
                                allDecrypted = false;
                            }
                        }
                    }
                    
                    if (allDecrypted) {
                        console.log(`  - ✅ All checked data in ${tableName} is decrypted`);
                    }
                }
                
                db.close();
                resolve();
            } catch (error) {
                console.error(`Error verifying ${dbPath}:`, error);
                db.close();
                reject(error);
            }
        });
    });
}

// Main function
async function main() {
    try {
        console.log("🔓 Starting database decryption for activity.db and history.db");
        
        for (const [dbName, config] of Object.entries(dbConfigs)) {
            const fullPath = path.join(__dirname, dbName);
            
            // Decrypt the database
            await decryptDatabase(fullPath, config);
            
            // Verify the decryption
            await verifyDecryption(fullPath, config);
        }
        
        console.log("\n✅ All databases processed and decrypted");
    } catch (error) {
        console.error("❌ Error during decryption process:", error);
    }
}

// Run the script
main(); 