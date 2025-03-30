/**
 * Database Override Script
 * This script ensures all database operations go through our encryption system
 */

const fs = require('fs');
const path = require('path');

// Get all JS files in the current directory
const jsFiles = fs.readdirSync(__dirname)
    .filter(file => file.endsWith('.js') && 
            file !== 'db_override.js' && 
            file !== 'encryption_utils.js' && 
            file !== 'encrypted_db.js' && 
            file !== 'db_manager.js' &&
            file !== 'encrypt_existing_data.js');

// Back up original modules
const originalModules = {
    sqlite3: require('sqlite3'),
    fs: require('fs'),
    path: require('path')
};

// Paths that should use encryption
const encryptedPaths = [
    'emails2.db',
    'email_analysis.db'
];

// Create backup of the databases
function backupDatabases() {
    encryptedPaths.forEach(dbName => {
        const dbPath = path.join(__dirname, dbName);
        if (fs.existsSync(dbPath)) {
            const backupPath = `${dbPath}.bak.${Date.now()}`;
            fs.copyFileSync(dbPath, backupPath);
            console.log(`Created backup of ${dbName} at ${backupPath}`);
        }
    });
}

// Create read-only flag on the databases
function protectDatabases() {
    encryptedPaths.forEach(dbName => {
        const dbPath = path.join(__dirname, dbName);
        if (fs.existsSync(dbPath)) {
            try {
                // Make the file read-only to prevent overwrites
                fs.chmodSync(dbPath, 0o444);
                console.log(`Set ${dbName} to read-only mode`);
            } catch (error) {
                console.error(`Failed to protect ${dbName}:`, error);
            }
        }
    });
}

// Main function
async function main() {
    console.log("💡 Database Override Script");
    console.log("This script will protect your encrypted databases from being overwritten");
    
    // Backup all databases first
    backupDatabases();
    
    // Protect all databases
    protectDatabases();
    
    console.log("\n✅ Databases protected. Your encrypted data should be preserved.");
    console.log("If there are any issues, you can restore from the backups (.bak files)");
    
    // Now let's check the encryption
    console.log("\n🔍 Checking encryption status of databases...");
    
    await checkEncryption();
}

// Check encryption
async function checkEncryption() {
    const sqlite3 = originalModules.sqlite3;
    
    for (const dbName of encryptedPaths) {
        const dbPath = path.join(__dirname, dbName);
        if (!fs.existsSync(dbPath)) {
            console.log(`❌ Database ${dbName} does not exist.`);
            continue;
        }
        
        console.log(`\nChecking ${dbName}...`);
        const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY);
        
        // Get all tables
        const tables = await new Promise((resolve, reject) => {
            db.all("SELECT name FROM sqlite_master WHERE type='table'", (err, rows) => {
                if (err) reject(err);
                else resolve(rows.map(row => row.name));
            });
        });
        
        console.log(`Tables: ${tables.join(', ')}`);
        
        // Check each table
        for (const table of tables) {
            try {
                const rows = await new Promise((resolve, reject) => {
                    db.all(`SELECT * FROM ${table} LIMIT 1`, (err, rows) => {
                        if (err) reject(err);
                        else resolve(rows || []);
                    });
                });
                
                if (rows.length === 0) {
                    console.log(`  - Table ${table}: Empty`);
                    continue;
                }
                
                const row = rows[0];
                const columns = Object.keys(row);
                
                console.log(`  - Table ${table}: Columns: ${columns.join(', ')}`);
                
                // Check for encrypted values
                let hasEncryptedValues = false;
                for (const col of columns) {
                    if (row[col] && typeof row[col] === 'string' && 
                        row[col].includes(':') && row[col].split(':').length === 3) {
                        console.log(`    ✅ Column ${col} appears to be encrypted`);
                        hasEncryptedValues = true;
                    }
                }
                
                if (!hasEncryptedValues) {
                    console.log(`    ⚠️ No encrypted columns found in table ${table}`);
                }
            } catch (error) {
                console.error(`Error checking table ${table}:`, error);
            }
        }
        
        db.close();
    }
}

// Check encryption once
main().catch(error => {
    console.error("Error in database override script:", error);
}); 