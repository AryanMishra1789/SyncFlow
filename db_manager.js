/**
 * Database Manager for Encrypted Databases
 * Provides centralized access to all databases with encryption support
 */

const path = require('path');
const EncryptedDatabase = require('./encrypted_db');
const encryption = require('./encryption_utils');

// Database configuration - defines which columns should be encrypted
const DB_CONFIG = {
    'history.db': {
        encryptedColumns: {
            history: ['url', 'website_name', 'domain'],
            recommendations: ['url', 'title', 'description']
        }
    },
    'emails2.db': {
        encryptedColumns: {
            emails: ['subject', 'body', 'sender', 'receiver', 'content'],
            threads: ['subject', 'snippet'],
            messages: ['subject', 'body', 'from', 'to', 'cc', 'bcc']
        }
    },
    'email_analysis.db': {
        encryptedColumns: {
            email_styles: ['style', 'formality', 'tone'],
            enhanched_email_styles: ['style_data'],
            contacts: ['email', 'name', 'frequency_data']
        }
    },
    'activity.db': {
        encryptedColumns: {
            activities: ['description', 'metadata']
        }
    }
};

class DatabaseManager {
    constructor() {
        this.databases = {};
        
        // Test encryption system
        if (!encryption.testEncryption()) {
            console.error('Encryption system test failed! Database encryption may not work properly.');
        } else {
            console.log('Encryption system initialized successfully');
        }
    }
    
    /**
     * Get a database connection
     * 
     * @param {string} dbName - Database filename
     * @returns {EncryptedDatabase} The database connection
     */
    getDatabase(dbName) {
        // Normalize the database name
        const baseName = path.basename(dbName);
        
        // Check if the database is already open
        if (this.databases[baseName]) {
            return this.databases[baseName];
        }
        
        // If path is absolute, use it directly; otherwise, make it relative to the app directory
        const dbPath = path.isAbsolute(dbName) ? dbName : path.join(__dirname, dbName);
        
        // Create a new encrypted database
        this.databases[baseName] = new EncryptedDatabase(dbPath);
        
        return this.databases[baseName];
    }
    
    /**
     * Check if a table exists in the database
     * 
     * @param {string} dbName - Database filename
     * @param {string} tableName - Table name to check
     * @returns {Promise<boolean>} Whether the table exists
     */
    async tableExists(dbName, tableName) {
        const db = this.getDatabase(dbName);
        try {
            const result = await db.get(
                `SELECT name FROM sqlite_master WHERE type='table' AND name=?`,
                [tableName]
            );
            return result !== null;
        } catch (error) {
            console.error(`Error checking if table ${tableName} exists:`, error);
            return false;
        }
    }
    
    /**
     * Check if a table has a column
     * 
     * @param {string} dbName - Database filename
     * @param {string} tableName - Table name to check
     * @param {string} columnName - Column name to check
     * @returns {Promise<boolean>} Whether the column exists
     */
    async columnExists(dbName, tableName, columnName) {
        const db = this.getDatabase(dbName);
        try {
            const result = await db.get(
                `PRAGMA table_info(${tableName})`,
                []
            );
            if (!result) return false;
            
            // Check columns in pragma results
            const columns = await db.all(`PRAGMA table_info(${tableName})`);
            return columns.some(col => col.name === columnName);
        } catch (error) {
            console.error(`Error checking if column ${columnName} exists:`, error);
            return false;
        }
    }
    
    /**
     * Close all database connections
     * 
     * @returns {Promise} A promise that resolves when all databases are closed
     */
    async closeAll() {
        const closePromises = [];
        
        for (const dbName in this.databases) {
            if (this.databases[dbName]) {
                closePromises.push(this.databases[dbName].close());
            }
        }
        
        await Promise.all(closePromises);
        this.databases = {};
    }
    
    /**
     * Insert data with encryption
     * 
     * @param {string} dbName - Database filename
     * @param {string} table - Table name
     * @param {Object} data - Data object to insert
     * @returns {Promise} A promise that resolves with the insert result
     */
    async insert(dbName, table, data) {
        const db = this.getDatabase(dbName);
        const baseName = path.basename(dbName);
        
        // Get list of columns that should be encrypted
        const encryptedColumns = DB_CONFIG[baseName]?.encryptedColumns?.[table] || [];
        
        return db.insertWithEncryption(table, data, encryptedColumns);
    }
    
    /**
     * Update data with encryption
     * 
     * @param {string} dbName - Database filename
     * @param {string} table - Table name
     * @param {Object} data - Data object to update
     * @param {string} whereClause - WHERE clause for the update
     * @param {Array} whereParams - Parameters for the WHERE clause
     * @returns {Promise} A promise that resolves with the update result
     */
    async update(dbName, table, data, whereClause, whereParams = []) {
        const db = this.getDatabase(dbName);
        const baseName = path.basename(dbName);
        
        // Get list of columns that should be encrypted
        const encryptedColumns = DB_CONFIG[baseName]?.encryptedColumns?.[table] || [];
        
        return db.updateWithEncryption(table, data, whereClause, whereParams, encryptedColumns);
    }
    
    /**
     * Query data with decryption
     * 
     * @param {string} dbName - Database filename
     * @param {string} sql - SQL query
     * @param {Array} params - Query parameters
     * @param {string} table - Optional table name for decryption configuration
     * @returns {Promise} A promise that resolves with the query results
     */
    async query(dbName, sql, params = [], table = null) {
        const db = this.getDatabase(dbName);
        const baseName = path.basename(dbName);
        
        // If table is provided, use its encryption config; otherwise, try to guess from SQL
        let encryptedColumns = [];
        if (table) {
            encryptedColumns = DB_CONFIG[baseName]?.encryptedColumns?.[table] || [];
        } else {
            // Try to extract table name from SQL
            const match = sql.match(/FROM\s+(\w+)/i);
            if (match && match[1]) {
                const extractedTable = match[1];
                encryptedColumns = DB_CONFIG[baseName]?.encryptedColumns?.[extractedTable] || [];
            }
        }
        
        return db.query(sql, params, encryptedColumns);
    }
    
    /**
     * Get a single row with decryption
     * 
     * @param {string} dbName - Database filename
     * @param {string} sql - SQL query
     * @param {Array} params - Query parameters
     * @param {string} table - Optional table name for decryption configuration
     * @returns {Promise} A promise that resolves with a single row
     */
    async get(dbName, sql, params = [], table = null) {
        const db = this.getDatabase(dbName);
        const baseName = path.basename(dbName);
        
        // Determine which columns should be decrypted
        let encryptedColumns = [];
        if (table) {
            encryptedColumns = DB_CONFIG[baseName]?.encryptedColumns?.[table] || [];
        } else {
            // Try to extract table name from SQL
            const match = sql.match(/FROM\s+(\w+)/i);
            if (match && match[1]) {
                const extractedTable = match[1];
                encryptedColumns = DB_CONFIG[baseName]?.encryptedColumns?.[extractedTable] || [];
            }
        }
        
        return db.get(sql, params, encryptedColumns);
    }
    
    /**
     * Run a raw SQL statement
     * 
     * @param {string} dbName - Database filename
     * @param {string} sql - SQL statement
     * @param {Array} params - Statement parameters
     * @returns {Promise} A promise that resolves with the result
     */
    async run(dbName, sql, params = []) {
        const db = this.getDatabase(dbName);
        return db.run(sql, params);
    }
    
    /**
     * Run a function within a transaction
     * 
     * @param {string} dbName - Database filename
     * @param {Function} fn - Function to run within the transaction
     * @returns {Promise} A promise that resolves with the function result
     */
    async inTransaction(dbName, fn) {
        const db = this.getDatabase(dbName);
        return db.inTransaction(fn);
    }
    
    /**
     * Get a list of encrypted columns for a table
     * 
     * @param {string} dbName - Database filename
     * @param {string} table - Table name
     * @returns {Array} Array of column names that should be encrypted
     */
    getEncryptedColumns(dbName, table) {
        const baseName = path.basename(dbName);
        return DB_CONFIG[baseName]?.encryptedColumns?.[table] || [];
    }
}

// Create and export a singleton instance
const dbManager = new DatabaseManager();
module.exports = dbManager; 