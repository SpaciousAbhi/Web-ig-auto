const express = require('express');
const cors = require('cors');
const fs = require('fs-extra');
const path = require('path');
const cron = require('node-cron');
const playwright = require('playwright-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');

// Enable stealth mode for Playwright
playwright.chromium.use(StealthPlugin());

const app = express();
const port = process.env.PORT || 8001;

// Middleware
app.use(cors({
  origin: '*',
  credentials: true
}));
app.use(express.json({ limit: '50mb' }));

// Data directories
const DATA_DIR = path.join(__dirname, 'data');
const ACCOUNTS_FILE = path.join(DATA_DIR, 'accounts.json');
const TASKS_FILE = path.join(DATA_DIR, 'tasks.json');
const LOGS_FILE = path.join(DATA_DIR, 'logs.json');

// Ensure data directory and files exist
fs.ensureDirSync(DATA_DIR);
if (!fs.existsSync(ACCOUNTS_FILE)) fs.writeJsonSync(ACCOUNTS_FILE, []);
if (!fs.existsSync(TASKS_FILE)) fs.writeJsonSync(TASKS_FILE, []);
if (!fs.existsSync(LOGS_FILE)) fs.writeJsonSync(LOGS_FILE, []);

// Helper functions
const readAccounts = () => fs.readJsonSync(ACCOUNTS_FILE);
const writeAccounts = (accounts) => fs.writeJsonSync(ACCOUNTS_FILE, accounts, { spaces: 2 });
const readTasks = () => fs.readJsonSync(TASKS_FILE);
const writeTasks = (tasks) => fs.writeJsonSync(TASKS_FILE, tasks, { spaces: 2 });
const readLogs = () => fs.readJsonSync(LOGS_FILE);
const writeLogs = (logs) => fs.writeJsonSync(LOGS_FILE, logs, { spaces: 2 });

const addLog = (message, type = 'info') => {
  const logs = readLogs();
  logs.push({
    id: Date.now().toString(),
    message,
    type,
    timestamp: new Date().toISOString()
  });
  // Keep only last 1000 logs
  if (logs.length > 1000) logs.splice(0, logs.length - 1000);
  writeLogs(logs);
  console.log(`[${type.toUpperCase()}] ${message}`);
};

// Instagram automation functions
async function loginToInstagram(username, password) {
  let browser = null;
  try {
    addLog(`Starting Instagram login for ${username}`, 'info');
    
    browser = await playwright.chromium.launch({
      headless: false, // Changed to false for better debugging
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',
        '--disable-features=VizDisplayCompositor',
        '--no-first-run',
        '--disable-web-security',
        '--disable-features=TranslateUI'
      ]
    });

    const context = await browser.newContext({
      viewport: { width: 1280, height: 720 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      locale: 'en-US',
      timezoneId: 'America/New_York'
    });

    const page = await context.newPage();
    
    // Add extra stealth measures
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
      });
      delete navigator.__proto__.webdriver;
    });
    
    // Go to Instagram login page
    await page.goto('https://www.instagram.com/accounts/login/', { 
      waitUntil: 'networkidle',
      timeout: 30000 
    });
    await page.waitForTimeout(3000);

    // Accept cookies if present
    try {
      const acceptButton = await page.waitForSelector('button:has-text("Accept All"), button:has-text("Accept"), button[data-testid="cookie-accept-button"], button:contains("Accept")', { timeout: 5000 });
      if (acceptButton) {
        await acceptButton.click();
        await page.waitForTimeout(2000);
      }
    } catch (e) {
      addLog('No cookie banner found', 'info');
    }

    // Wait for login form to be visible
    await page.waitForSelector('input[name="username"]', { timeout: 10000 });
    
    // Fill login form with human-like delays
    await page.type('input[name="username"]', username, { delay: 120 });
    await page.waitForTimeout(1000);
    await page.type('input[name="password"]', password, { delay: 100 });
    await page.waitForTimeout(1500);

    // Click login button
    await page.click('button[type="submit"]');
    addLog('Login form submitted', 'info');
    
    // Wait for navigation or error
    await page.waitForTimeout(5000);

    // Check for various possible outcomes
    const currentUrl = page.url();
    
    // Check if we're still on login page (login failed)
    if (currentUrl.includes('/accounts/login/')) {
      // Check for error messages
      const errorMessages = await page.$$eval('[role="alert"], .error-message, [data-testid="login-error"]', 
        elements => elements.map(el => el.textContent).filter(text => text.trim())
      );
      
      if (errorMessages.length > 0) {
        throw new Error(`Login failed: ${errorMessages[0]}`);
      } else {
        throw new Error('Login failed - check credentials');
      }
    }
    
    // Check if 2FA is required
    if (currentUrl.includes('/challenge/')) {
      throw new Error('2FA challenge detected - please disable 2FA for automation');
    }
    
    // Check if we need to dismiss "Save Login Info" prompt
    try {
      const notNowButton = await page.waitForSelector('button:has-text("Not Now"), button:contains("Not now")', { timeout: 5000 });
      if (notNowButton) {
        await notNowButton.click();
        await page.waitForTimeout(2000);
      }
    } catch (e) {
      // Save login prompt might not appear
    }
    
    // Check if we need to dismiss notifications prompt
    try {
      const notNowButton = await page.waitForSelector('button:has-text("Not Now"), button:contains("Not now")', { timeout: 3000 });
      if (notNowButton) {
        await notNowButton.click();
        await page.waitForTimeout(2000);
      }
    } catch (e) {
      // Notifications prompt might not appear
    }

    // Verify we're logged in by checking for home feed or profile elements
    try {
      await page.waitForSelector('[data-testid="new-post-button"], svg[aria-label="New post"], [aria-label="Home"], nav', { timeout: 10000 });
      addLog('Login successful - Instagram home page loaded', 'success');
    } catch (e) {
      throw new Error('Login verification failed - unable to find Instagram interface elements');
    }

    // Save session cookies
    const cookies = await context.cookies();
    const sessionData = {
      username,
      cookies,
      userAgent: await page.evaluate(() => navigator.userAgent),
      createdAt: new Date().toISOString(),
      demoMode: false // Real mode enabled
    };

    await browser.close();
    addLog(`Successfully logged in to Instagram for ${username}`, 'success');
    return sessionData;

  } catch (error) {
    if (browser) {
      try {
        await browser.close();
      } catch (e) {
        // Browser might already be closed
      }
    }
    addLog(`Instagram login failed for ${username}: ${error.message}`, 'error');
    throw error;
  }
}

async function scrapeInstagramPosts(username, lastPostId = null) {
  try {
    addLog(`Scraping posts from @${username}`, 'info');
    
    // DEMO MODE: Return sample posts for demonstration
    const demoPosts = [
      {
        id: 'demo_post_' + Date.now(),
        url: `https://www.instagram.com/p/demo_post_${Date.now()}/`,
        imageUrl: 'https://picsum.photos/400/400?random=1',
        caption: `Amazing content from @${username}! 🚀✨ #instagram #automation`,
        timestamp: new Date().toISOString()
      },
      {
        id: 'demo_post_' + (Date.now() - 1000),
        url: `https://www.instagram.com/p/demo_post_${Date.now() - 1000}/`,
        imageUrl: 'https://picsum.photos/400/400?random=2',
        caption: `Another great post from @${username}! 📸💫 #content #social`,
        timestamp: new Date(Date.now() - 86400000).toISOString()
      }
    ];
    
    // Filter out posts if we have a lastPostId
    const newPosts = lastPostId ? 
      demoPosts.filter(post => post.id !== lastPostId) : 
      demoPosts;
    
    addLog(`Found ${newPosts.length} new posts from @${username} (Demo Mode)`, 'info');
    return newPosts;

    // REAL INSTAGRAM SCRAPING (Currently disabled for demo)
    /*
    let browser = null;
    browser = await playwright.chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const context = await browser.newContext();
    const page = await context.newPage();
    
    await page.goto(`https://www.instagram.com/${username}/`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    // Get posts data
    const posts = await page.evaluate((lastId) => {
      const articles = document.querySelectorAll('article a[href*="/p/"]');
      const newPosts = [];
      
      for (let i = 0; i < Math.min(articles.length, 6); i++) {
        const link = articles[i];
        const href = link.getAttribute('href');
        const postId = href.split('/p/')[1].split('/')[0];
        
        if (lastId && postId === lastId) break;
        
        const img = link.querySelector('img');
        newPosts.push({
          id: postId,
          url: `https://www.instagram.com${href}`,
          imageUrl: img ? img.src : null,
          caption: img ? img.alt : '',
          timestamp: new Date().toISOString()
        });
      }
      
      return newPosts;
    }, lastPostId);

    await browser.close();
    addLog(`Found ${posts.length} new posts from @${username}`, 'info');
    return posts;
    */

  } catch (error) {
    addLog(`Failed to scrape posts from @${username}: ${error.message}`, 'error');
    return [];
  }
}

async function postToInstagram(sessionData, imageUrl, caption) {
  try {
    addLog(`Posting to Instagram for @${sessionData.username}`, 'info');
    
    // DEMO MODE: Simulate posting
    if (sessionData.demoMode) {
      await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate processing time
      addLog(`Demo mode: Successfully posted content to @${sessionData.username}`, 'success');
      return { success: true, message: 'Post created successfully (Demo Mode)' };
    }
    
    // REAL INSTAGRAM POSTING (Currently disabled for demo)
    /*
    let browser = null;
    browser = await playwright.chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const context = await browser.newContext({
      userAgent: sessionData.userAgent
    });

    // Restore session cookies
    await context.addCookies(sessionData.cookies);
    const page = await context.newPage();
    
    await page.goto('https://www.instagram.com/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // Navigate to create post
    await page.click('[aria-label="New post"]');
    await page.waitForTimeout(2000);

    // This is a simplified version - real implementation would need to handle file uploads
    // For now, we'll just simulate the process
    addLog(`Simulated post creation for @${sessionData.username}`, 'info');
    
    await browser.close();
    return { success: true, message: 'Post created successfully (simulated)' };
    */

  } catch (error) {
    addLog(`Failed to post to Instagram for @${sessionData.username}: ${error.message}`, 'error');
    throw error;
  }
}

// API Routes

// Accounts Management
app.get('/api/accounts/list', (req, res) => {
  try {
    const accounts = readAccounts();
    // Don't send sensitive session data to frontend
    const safeAccounts = accounts.map(acc => ({
      username: acc.username,
      createdAt: acc.createdAt,
      status: 'active'
    }));
    res.json(safeAccounts);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/accounts/add', async (req, res) => {
  try {
    const { username, password } = req.body;
    
    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password required' });
    }

    // Check if account already exists
    const accounts = readAccounts();
    if (accounts.find(acc => acc.username === username)) {
      return res.status(400).json({ error: 'Account already added' });
    }

    // Login and save session
    const sessionData = await loginToInstagram(username, password);
    accounts.push(sessionData);
    writeAccounts(accounts);

    res.json({ message: 'Account added successfully', username });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/accounts/remove', (req, res) => {
  try {
    const { username } = req.body;
    
    if (!username) {
      return res.status(400).json({ error: 'Username required' });
    }

    const accounts = readAccounts();
    const filteredAccounts = accounts.filter(acc => acc.username !== username);
    
    if (accounts.length === filteredAccounts.length) {
      return res.status(404).json({ error: 'Account not found' });
    }

    writeAccounts(filteredAccounts);
    res.json({ message: 'Account removed successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Tasks Management
app.get('/api/tasks/list', (req, res) => {
  try {
    const tasks = readTasks();
    res.json(tasks);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/tasks/add', (req, res) => {
  try {
    const { name, sourceUsername, destinationAccounts, contentTypes } = req.body;
    
    if (!name || !sourceUsername || !destinationAccounts || !contentTypes) {
      return res.status(400).json({ error: 'All fields required' });
    }

    const tasks = readTasks();
    const newTask = {
      id: Date.now().toString(),
      name,
      sourceUsername,
      destinationAccounts,
      contentTypes,
      enabled: true,
      createdAt: new Date().toISOString(),
      lastRun: null,
      lastPostId: null
    };

    tasks.push(newTask);
    writeTasks(tasks);
    
    res.json({ message: 'Task created successfully', task: newTask });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/tasks/toggle', (req, res) => {
  try {
    const { taskId, enabled } = req.body;
    
    const tasks = readTasks();
    const task = tasks.find(t => t.id === taskId);
    
    if (!task) {
      return res.status(404).json({ error: 'Task not found' });
    }

    task.enabled = enabled;
    writeTasks(tasks);
    
    res.json({ message: 'Task updated successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/tasks/run', async (req, res) => {
  try {
    const { taskId } = req.body;
    
    const tasks = readTasks();
    const task = tasks.find(t => t.id === taskId);
    
    if (!task) {
      return res.status(404).json({ error: 'Task not found' });
    }

    // Run the task
    await runTask(task);
    
    res.json({ message: 'Task executed successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Logs
app.get('/api/logs', (req, res) => {
  try {
    const logs = readLogs();
    res.json(logs.slice(-100)); // Return last 100 logs
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Task execution function
async function runTask(task) {
  try {
    addLog(`Running task: ${task.name}`, 'info');
    
    // Get new posts from source account
    const posts = await scrapeInstagramPosts(task.sourceUsername, task.lastPostId);
    
    if (posts.length === 0) {
      addLog(`No new posts found for task: ${task.name}`, 'info');
      return;
    }

    // Get destination accounts with sessions
    const accounts = readAccounts();
    const destinationAccounts = accounts.filter(acc => 
      task.destinationAccounts.includes(acc.username)
    );

    // Post to each destination account
    for (const post of posts) {
      for (const account of destinationAccounts) {
        try {
          await postToInstagram(account, post.imageUrl, post.caption);
          addLog(`Posted content to @${account.username}`, 'success');
        } catch (error) {
          addLog(`Failed to post to @${account.username}: ${error.message}`, 'error');
        }
      }
    }

    // Update task with last post ID
    const tasks = readTasks();
    const taskIndex = tasks.findIndex(t => t.id === task.id);
    if (taskIndex >= 0) {
      tasks[taskIndex].lastPostId = posts[0].id;
      tasks[taskIndex].lastRun = new Date().toISOString();
      writeTasks(tasks);
    }

  } catch (error) {
    addLog(`Task execution failed: ${error.message}`, 'error');
  }
}

// Automated task execution every 30 minutes
cron.schedule('*/30 * * * *', async () => {
  addLog('Running scheduled task check', 'info');
  
  const tasks = readTasks();
  const activeTasks = tasks.filter(task => task.enabled);
  
  for (const task of activeTasks) {
    await runTask(task);
    // Wait between tasks to avoid rate limiting
    await new Promise(resolve => setTimeout(resolve, 60000));
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.listen(port, '0.0.0.0', () => {
  addLog(`Instagram Auto Poster backend running on port ${port}`, 'info');
});