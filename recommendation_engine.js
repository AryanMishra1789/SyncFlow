const { spawn } = require('child_process');
const path = require('path');
const dbManager = require('./db_manager');

class RecommendationEngine {
    constructor() {
        this.pythonProcess = null;
        this.cachedRecommendations = null;
        this.lastFetchTime = null;
        this.fetchInterval = 10 * 60 * 1000; // 10 minutes in milliseconds
    }

    async generate_recommendations(options = {}) {
        try {
            // If we have cached recommendations that aren't expired, use them
            const currentTime = new Date().getTime();
            if (!options.forceRefresh && 
                this.cachedRecommendations && 
                this.lastFetchTime && 
                (currentTime - this.lastFetchTime) < this.fetchInterval) {
                console.log('Using cached recommendations');
                return this.cachedRecommendations;
            }

            const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
            const scriptPath = path.join(__dirname, 'enhanced_recommendations.py');
            
            const args = [scriptPath];
            
            // Add excluded URLs if provided
            if (options.exclude && Array.isArray(options.exclude) && options.exclude.length > 0) {
                args.push('--exclude');
                args.push(options.exclude.join(','));
            }
            
            return new Promise((resolve, reject) => {
                const pythonProcess = spawn(pythonPath, args);
                let jsonOutput = '';
                let errorOutput = '';

                pythonProcess.stdout.on('data', (data) => {
                    jsonOutput += data.toString();
                });

                pythonProcess.stderr.on('data', (data) => {
                    console.error(`Python stderr: ${data}`);
                    errorOutput += data.toString();
                });

                pythonProcess.on('close', (code) => {
                    if (code !== 0) {
                        console.error('Python process failed:', errorOutput);
                        // Return default recommendations on error
                        resolve([{
                            url: "https://github.com/explore",
                            title: "GitHub Explore",
                            category: "Technology",
                            confidence: 80,
                            description: "Explore trending repositories"
                        }]);
                        return;
                    }

                    try {
                        const result = JSON.parse(jsonOutput.trim());
                        
                        // Cache the recommendations
                        this.cachedRecommendations = result.recommendations;
                        this.lastFetchTime = currentTime;
                        
                        resolve(result.recommendations);
                    } catch (error) {
                        console.error('Failed to parse recommendations:', error);
                        console.error('Raw output:', jsonOutput);
                        // Return default recommendations on parse error
                        resolve([{
                            url: "https://github.com/explore",
                            title: "GitHub Explore",
                            category: "Technology",
                            confidence: 80,
                            description: "Explore trending repositories"
                        }]);
                    }
                });

                pythonProcess.on('error', (error) => {
                    console.error('Failed to start Python process:', error);
                    // Return default recommendations on process error
                    resolve([{
                        url: "https://github.com/explore",
                        title: "GitHub Explore",
                        category: "Technology",
                        confidence: 80,
                        description: "Explore trending repositories"
                    }]);
                });
            });
        } catch (error) {
            console.error('Error in generate_recommendations:', error);
            // Return default recommendations on any error
            return [{
                url: "https://github.com/explore",
                title: "GitHub Explore",
                category: "Technology",
                confidence: 80,
                description: "Explore trending repositories"
            }];
        }
    }

    async get_trending_recommendations(category = null, limit = 4) {
        try {
            let query, params = [];
            
            if (category && category !== 'all') {
                query = `
                    SELECT id, title, url, description, category, confidence, timestamp 
                    FROM recommendations 
                    WHERE category = ? 
                    ORDER BY confidence DESC, timestamp DESC 
                    LIMIT ?
                `;
                params = [category, limit];
            } else {
                query = `
                    SELECT id, title, url, description, category, confidence, timestamp 
                    FROM recommendations 
                    ORDER BY confidence DESC, timestamp DESC 
                    LIMIT ?
                `;
                params = [limit];
            }
            
            const trending = await dbManager.query('history.db', query, params, 'recommendations');
            return trending;
        } catch (error) {
            console.error('Error getting trending recommendations:', error);
            return [];
        }
    }

    async analyze_user_history() {
        try {
            console.log('Analyzing user history...');
            const result = await this._runPythonScript('analyze_history');
            if (result) {
                console.log('Successfully analyzed user history');
                return result;
            }
            throw new Error('No analysis results returned');
        } catch (error) {
            console.error('Error analyzing history:', error);
            return null;
        }
    }

    _runPythonScript(method) {
        return new Promise((resolve, reject) => {
            const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
            const scriptPath = path.join(__dirname, 'recommendation_engine.py');
            
            console.log(`Running Python script: ${scriptPath} with method: ${method}`);
            
            const pythonProcess = spawn(pythonPath, [scriptPath, method]);
            let jsonOutput = '';
            let errorOutput = '';

            pythonProcess.stdout.on('data', (data) => {
                const output = data.toString();
                jsonOutput += output;
            });

            pythonProcess.stderr.on('data', (data) => {
                const error = data.toString();
                console.error(`Python stderr: ${error}`);
                errorOutput += error;
            });

            pythonProcess.on('close', (code) => {
                console.log(`Python process exited with code ${code}`);
                if (code !== 0) {
                    reject(new Error(`Python process failed with code ${code}. Error: ${errorOutput}`));
                    return;
                }

                try {
                    // Try to parse the JSON output
                    const trimmedOutput = jsonOutput.trim();
                    if (!trimmedOutput) {
                        reject(new Error('No output from Python script'));
                        return;
                    }
                    const result = JSON.parse(trimmedOutput);
                    resolve(result);
                } catch (error) {
                    console.error('Failed to parse Python output:', error);
                    console.error('Raw output:', jsonOutput);
                    reject(new Error('Failed to parse Python output'));
                }
            });

            pythonProcess.on('error', (error) => {
                console.error('Failed to start Python process:', error);
                reject(error);
            });
        });
    }

    // Get recommendations from the database using encrypted storage
    async get_recommendations_from_db() {
        try {
            // Get recommendations from database
            const recommendations = await dbManager.query(
                'history.db', 
                `SELECT id, title, url, description, category, confidence, timestamp, is_visited
                FROM recommendations
                ORDER BY confidence DESC`,
                [],
                'recommendations'
            );
            
            return recommendations;
        } catch (error) {
            console.error('Error getting recommendations from DB:', error);
            return [];
        }
    }
    
    // Mark a recommendation as visited
    async mark_recommendation_visited(recId) {
        try {
            await dbManager.update('history.db', 'recommendations', 
                { is_visited: 1 }, 
                'id = ?', 
                [recId]
            );
            return { success: true };
        } catch (error) {
            console.error('Error marking recommendation as visited:', error);
            return { success: false, error: error.message };
        }
    }
}

module.exports = { RecommendationEngine }; 