/**
 * Encrypted Database Wrapper
 * Provides encrypted read/write operations for SQLite databases
 */

const sqlite3 = require('sqlite3').verbose();
const encryption = require('./encryption_utils');
const path = require('path');

class EncryptedDatabase {
    /**
     * Create a new encrypted database wrapper
     * 
     * @param {string} dbPath - Path to the database file
     */
    constructor(dbPath) {
        this.dbPath = dbPath;
        this.db = new sqlite3.Database(dbPath, (err) => {
            if (err) {
                console.error(`Error opening database ${dbPath}:`, err);
            } else {
                console.log(`Connected to encrypted database: ${dbPath}`);
            }
        });
    }

    /**
     * Close the database connection
     * 
     * @returns {Promise} A promise that resolves when the database is closed
     */
    close() {
        return new Promise((resolve, reject) => {
            this.db.close((err) => {
                if (err) {
                    console.error(`Error closing database ${this.dbPath}:`, err);
                    reject(err);
                } else {
                    console.log(`Closed encrypted database: ${this.dbPath}`);
                    resolve();
                }
            });
        });
    }

    /**
     * Execute an SQL statement with optional parameters
     * 
     * @param {string} sql - The SQL statement to run
     * @param {Array} params - The parameters for the SQL statement
     * @returns {Promise} A promise that resolves when the statement completes
     */
    run(sql, params = []) {
        return new Promise((resolve, reject) => {
            this.db.run(sql, params, function(err) {
                if (err) {
                    console.error(`Error executing SQL (${sql}):`, err);
                    reject(err);
                } else {
                    resolve({ lastID: this.lastID, changes: this.changes });
                }
            });
        });
    }

    /**
     * Check if a string value appears to be encrypted in our format
     * 
     * @param {string} value - The value to check
     * @returns {boolean} Whether the value appears to be encrypted
     */
    isEncrypted(value) {
        if (!value || typeof value !== 'string') return false;
        
        // Our encrypted format is: iv:authTag:encryptedData
        // Each part should be a hex string
        const parts = value.split(':');
        if (parts.length !== 3) return false;
        
        // The IV should be 32 characters (16 bytes in hex)
        // The auth tag should be 32 characters (16 bytes in hex)
        // The encrypted data part should exist
        return (
            parts[0].length === 32 && 
            /^[0-9a-f]+$/i.test(parts[0]) &&
            parts[1].length === 32 && 
            /^[0-9a-f]+$/i.test(parts[1]) &&
            parts[2].length > 0
        );
    }

    /**
     * Get a single row from the database
     * 
     * @param {string} sql - The SQL query to run
     * @param {Array} params - The parameters for the SQL statement
     * @param {Array} encryptedColumns - Array of column names to decrypt
     * @returns {Promise} A promise that resolves with the row
     */
    get(sql, params = [], encryptedColumns = []) {
        return new Promise((resolve, reject) => {
            this.db.get(sql, params, (err, row) => {
                if (err) {
                    console.error(`Error executing SQL (${sql}):`, err);
                    reject(err);
                } else if (!row) {
                    resolve(null);
                } else {
                    // Decrypt encrypted columns
                    if (encryptedColumns.length > 0) {
                        for (const col of encryptedColumns) {
                            if (row[col] && typeof row[col] === 'string') {
                                // Check if the data appears to be encrypted (has our format)
                                if (this.isEncrypted(row[col])) {
                                    try {
                                        const decrypted = encryption.decrypt(row[col]);
                                        if (decrypted !== null) {
                                            row[col] = decrypted;
                                        }
                                        // If decryption returns null, keep the original value
                                    } catch (decryptErr) {
                                        // Silent failure - keep original value
                                        // This allows handling of existing unencrypted data
                                    }
                                }
                            }
                        }
                    }
                    resolve(row);
                }
            });
        });
    }

    /**
     * Get all rows from the database matching the query
     * 
     * @param {string} sql - The SQL query to run
     * @param {Array} params - The parameters for the SQL statement
     * @param {Array} encryptedColumns - Array of column names to decrypt
     * @returns {Promise} A promise that resolves with an array of rows
     */
    all(sql, params = [], encryptedColumns = []) {
        return new Promise((resolve, reject) => {
            this.db.all(sql, params, (err, rows) => {
                if (err) {
                    console.error(`Error executing SQL (${sql}):`, err);
                    reject(err);
                } else {
                    // Decrypt encrypted columns
                    if (encryptedColumns.length > 0 && rows.length > 0) {
                        for (const row of rows) {
                            for (const col of encryptedColumns) {
                                if (row[col] && typeof row[col] === 'string') {
                                    // Check if the data appears to be encrypted (has our format)
                                    if (this.isEncrypted(row[col])) {
                                        try {
                                            const decrypted = encryption.decrypt(row[col]);
                                            if (decrypted !== null) {
                                                row[col] = decrypted;
                                            }
                                            // If decryption returns null, keep the original value
                                        } catch (decryptErr) {
                                            // Silent failure - keep original value
                                            // This allows handling of existing unencrypted data
                                        }
                                    }
                                }
                            }
                        }
                    }
                    resolve(rows);
                }
            });
        });
    }

    /**
     * Insert data with encryption
     * 
     * @param {string} table - Table name
     * @param {Object} data - Data object with column:value pairs
     * @param {Array} encryptedColumns - Array of column names to encrypt
     * @returns {Promise} A promise that resolves with the lastID
     */
    async insertWithEncryption(table, data, encryptedColumns = []) {
        // Create a copy of the data to avoid modifying the original
        const encryptedData = {...data};
        
        // Encrypt specified columns
        for (const col of encryptedColumns) {
            if (encryptedData[col] !== undefined && encryptedData[col] !== null) {
                if (typeof encryptedData[col] === 'object') {
                    encryptedData[col] = encryption.encryptObject(encryptedData[col]);
                } else {
                    encryptedData[col] = encryption.encrypt(encryptedData[col].toString());
                }
            }
        }
        
        // Generate column names and placeholders
        const columns = Object.keys(encryptedData);
        const placeholders = columns.map(() => '?').join(',');
        const values = columns.map(col => encryptedData[col]);
        
        // Create and execute SQL statement
        const sql = `INSERT INTO ${table} (${columns.join(',')}) VALUES (${placeholders})`;
        const result = await this.run(sql, values);
        return result;
    }

    /**
     * Update data with encryption
     * 
     * @param {string} table - Table name
     * @param {Object} data - Data object with column:value pairs to update
     * @param {string} whereClause - WHERE clause for the update (without 'WHERE')
     * @param {Array} whereParams - Parameters for the WHERE clause
     * @param {Array} encryptedColumns - Array of column names to encrypt
     * @returns {Promise} A promise that resolves with the changes count
     */
    async updateWithEncryption(table, data, whereClause, whereParams = [], encryptedColumns = []) {
        // Create a copy of the data to avoid modifying the original
        const encryptedData = {...data};
        
        // Encrypt specified columns
        for (const col of encryptedColumns) {
            if (encryptedData[col] !== undefined && encryptedData[col] !== null) {
                if (typeof encryptedData[col] === 'object') {
                    encryptedData[col] = encryption.encryptObject(encryptedData[col]);
                } else {
                    encryptedData[col] = encryption.encrypt(encryptedData[col].toString());
                }
            }
        }
        
        // Generate SET clause
        const columns = Object.keys(encryptedData);
        const setClause = columns.map(col => `${col} = ?`).join(',');
        const values = columns.map(col => encryptedData[col]);
        
        // Add WHERE parameters
        const allParams = [...values, ...whereParams];
        
        // Create and execute SQL statement
        const sql = `UPDATE ${table} SET ${setClause} WHERE ${whereClause}`;
        const result = await this.run(sql, allParams);
        return result;
    }

    /**
     * Execute an SQL query with parameters and return multiple rows
     * 
     * @param {string} sql - The SQL query
     * @param {Array} params - Array of parameters
     * @param {Array} encryptedColumns - Array of column names to decrypt
     * @returns {Promise<Array>} A promise that resolves with the rows
     */
    query(sql, params = [], encryptedColumns = []) {
        return this.all(sql, params, encryptedColumns);
    }

    /**
     * Begin a database transaction
     * 
     * @returns {Promise} A promise that resolves when the transaction begins
     */
    beginTransaction() {
        return this.run('BEGIN TRANSACTION');
    }

    /**
     * Commit a database transaction
     * 
     * @returns {Promise} A promise that resolves when the transaction is committed
     */
    commit() {
        return this.run('COMMIT');
    }

    /**
     * Roll back a database transaction
     * 
     * @returns {Promise} A promise that resolves when the transaction is rolled back
     */
    rollback() {
        return this.run('ROLLBACK');
    }

    /**
     * Run a function within a transaction
     * 
     * @param {Function} fn - The function to run inside a transaction. Should return a Promise.
     * @returns {Promise} A promise that resolves with the result of the function
     */
    async inTransaction(fn) {
        await this.beginTransaction();
        try {
            const result = await fn();
            await this.commit();
            return result;
        } catch (error) {
            await this.rollback();
            throw error;
        }
    }
}

module.exports = EncryptedDatabase; 