import React, { useState, useEffect } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [activeTab, setActiveTab] = useState('accounts');
  const [accounts, setAccounts] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  // Account form state
  const [newAccount, setNewAccount] = useState({ username: '', password: '' });
  
  // Task form state
  const [newTask, setNewTask] = useState({
    name: '',
    sourceUsername: [], // Changed to array for multiple sources
    destinationAccounts: [],
    contentTypes: {
      posts: true,
      reels: false,
      stories: false
    }
  });

  useEffect(() => {
    fetchAccounts();
    fetchTasks();
    fetchLogs();
  }, []);

  const fetchAccounts = async () => {
    try {
      const response = await fetch(`${API}/accounts/list`);
      const data = await response.json();
      setAccounts(data);
    } catch (error) {
      console.error('Error fetching accounts:', error);
    }
  };

  const fetchTasks = async () => {
    try {
      const response = await fetch(`${API}/tasks/list`);
      const data = await response.json();
      setTasks(data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const fetchLogs = async () => {
    try {
      const response = await fetch(`${API}/logs`);
      const data = await response.json();
      setLogs(data);
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  const addAccount = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch(`${API}/accounts/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newAccount)
      });
      
      const data = await response.json();
      
      if (response.ok) {
        alert('Account added successfully!');
        setNewAccount({ username: '', password: '' });
        fetchAccounts();
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const removeAccount = async (username) => {
    if (!confirm(`Remove account @${username}?`)) return;
    
    try {
      const response = await fetch(`${API}/accounts/remove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username })
      });
      
      if (response.ok) {
        fetchAccounts();
      } else {
        const data = await response.json();
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  };

  const addTask = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch(`${API}/tasks/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTask)
      });
      
      const data = await response.json();
      
      if (response.ok) {
        alert('Task created successfully!');
        setNewTask({
          name: '',
          sourceUsername: [],
          destinationAccounts: [],
          contentTypes: { posts: true, reels: false, stories: false }
        });
        fetchTasks();
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const toggleTask = async (taskId, enabled) => {
    try {
      const response = await fetch(`${API}/tasks/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ taskId, enabled })
      });
      
      if (response.ok) {
        fetchTasks();
      }
    } catch (error) {
      console.error('Error toggling task:', error);
    }
  };

  const runTask = async (taskId) => {
    if (!confirm('Run task now?')) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${API}/tasks/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ taskId })
      });
      
      if (response.ok) {
        alert('Task executed successfully!');
        fetchLogs();
      } else {
        const data = await response.json();
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900">
      {/* Header */}
      <div className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-r from-pink-500 to-orange-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">IG</span>
              </div>
              <h1 className="text-xl font-bold text-white">Auto Poster Dashboard</h1>
            </div>
            <div className="text-sm text-gray-300">
              {accounts.length} accounts • {tasks.length} tasks
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Navigation */}
        <div className="flex space-x-1 bg-black/20 backdrop-blur-sm rounded-lg p-1 mb-8">
          {['accounts', 'tasks', 'logs'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all duration-200 ${
                activeTab === tab
                  ? 'bg-white text-gray-900 shadow-lg'
                  : 'text-gray-300 hover:text-white hover:bg-white/10'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Accounts Tab */}
        {activeTab === 'accounts' && (
          <div className="space-y-6">
            {/* Add Account Form */}
            <div className="bg-black/20 backdrop-blur-sm rounded-xl p-6 border border-white/10">
              <h2 className="text-xl font-semibold text-white mb-4">Add Instagram Account</h2>
              <form onSubmit={addAccount} className="space-y-4">
                <div>
                  <input
                    type="text"
                    placeholder="Instagram Username"
                    value={newAccount.username}
                    onChange={(e) => setNewAccount({...newAccount, username: e.target.value})}
                    className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <input
                    type="password"
                    placeholder="Password"
                    value={newAccount.password}
                    onChange={(e) => setNewAccount({...newAccount, password: e.target.value})}
                    className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-pink-500 to-orange-500 text-white py-3 px-6 rounded-lg font-medium hover:from-pink-600 hover:to-orange-600 transition-all duration-200 disabled:opacity-50"
                >
                  {loading ? 'Adding Account...' : 'Add Account'}
                </button>
              </form>
            </div>

            {/* Accounts List */}
            <div className="bg-black/20 backdrop-blur-sm rounded-xl p-6 border border-white/10">
              <h2 className="text-xl font-semibold text-white mb-4">Destination Accounts</h2>
              {accounts.length === 0 ? (
                <p className="text-gray-400">No accounts added yet</p>
              ) : (
                <div className="space-y-3">
                  {accounts.map((account, index) => (
                    <div key={index} className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10">
                      <div>
                        <p className="text-white font-medium">@{account.username}</p>
                        <p className="text-gray-400 text-sm">Added {new Date(account.createdAt).toLocaleDateString()}</p>
                      </div>
                      <button
                        onClick={() => removeAccount(account.username)}
                        className="text-red-400 hover:text-red-300 font-medium"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tasks Tab */}
        {activeTab === 'tasks' && (
          <div className="space-y-6">
            {/* Add Task Form */}
            <div className="bg-black/20 backdrop-blur-sm rounded-xl p-6 border border-white/10">
              <h2 className="text-xl font-semibold text-white mb-4">Create New Task</h2>
              <form onSubmit={addTask} className="space-y-4">
                <div>
                  <input
                    type="text"
                    placeholder="Task Name"
                    value={newTask.name}
                    onChange={(e) => setNewTask({...newTask, name: e.target.value})}
                    className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-white mb-2">Source Instagram Usernames</label>
                  <div className="space-y-2">
                    <input
                      type="text"
                      placeholder="Enter source accounts separated by commas (e.g. natgeo, bbcearth, discovery)"
                      value={Array.isArray(newTask.sourceUsername) ? newTask.sourceUsername.join(', ') : newTask.sourceUsername}
                      onChange={(e) => {
                        const accounts = e.target.value.split(',').map(acc => acc.trim()).filter(acc => acc);
                        setNewTask({...newTask, sourceUsername: accounts});
                      }}
                      className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      required
                    />
                    <p className="text-sm text-gray-400">
                      💡 Add multiple source accounts separated by commas. The system will monitor ALL of them and auto-post any new content.
                    </p>
                  </div>
                </div>
                <div>
                  <label className="block text-white mb-2">Destination Accounts</label>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {accounts.map((account, index) => (
                      <label key={index} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={newTask.destinationAccounts.includes(account.username)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewTask({
                                ...newTask,
                                destinationAccounts: [...newTask.destinationAccounts, account.username]
                              });
                            } else {
                              setNewTask({
                                ...newTask,
                                destinationAccounts: newTask.destinationAccounts.filter(u => u !== account.username)
                              });
                            }
                          }}
                          className="rounded border-gray-300"
                        />
                        <span className="text-white">@{account.username}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-white mb-2">Content Types</label>
                  <div className="flex space-x-4">
                    {Object.entries(newTask.contentTypes).map(([type, checked]) => (
                      <label key={type} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => setNewTask({
                            ...newTask,
                            contentTypes: { ...newTask.contentTypes, [type]: e.target.checked }
                          })}
                          className="rounded border-gray-300"
                        />
                        <span className="text-white capitalize">{type}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={loading || accounts.length === 0}
                  className="w-full bg-gradient-to-r from-blue-500 to-purple-500 text-white py-3 px-6 rounded-lg font-medium hover:from-blue-600 hover:to-purple-600 transition-all duration-200 disabled:opacity-50"
                >
                  {loading ? 'Creating Task...' : 'Create Task'}
                </button>
              </form>
            </div>

            {/* Tasks List */}
            <div className="bg-black/20 backdrop-blur-sm rounded-xl p-6 border border-white/10">
              <h2 className="text-xl font-semibold text-white mb-4">Active Tasks</h2>
              {tasks.length === 0 ? (
                <p className="text-gray-400">No tasks created yet</p>
              ) : (
                <div className="space-y-4">
                  {tasks.map((task) => (
                    <div key={task.id} className="p-4 bg-white/5 rounded-lg border border-white/10">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-white font-medium">{task.name}</h3>
                        <div className="flex items-center space-x-3">
                          <label className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={task.enabled}
                              onChange={(e) => toggleTask(task.id, e.target.checked)}
                              className="rounded border-gray-300"
                            />
                            <span className="text-sm text-gray-300">Enabled</span>
                          </label>
                          <button
                            onClick={() => runTask(task.id)}
                            className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700"
                          >
                            Run Now
                          </button>
                        </div>
                      </div>
                      <div className="text-sm text-gray-400 space-y-1">
                        <p>Source: @{task.sourceUsername}</p>
                        <p>Destinations: {task.destinationAccounts.join(', ')}</p>
                        <p>Content: {Object.entries(task.contentTypes).filter(([_, enabled]) => enabled).map(([type]) => 
                          type.charAt(0).toUpperCase() + type.slice(1)
                        ).join(', ')}</p>
                        {task.lastRun && <p>Last run: {new Date(task.lastRun).toLocaleString()}</p>}
                        {task.lastProcessedCount && <p>Last processed: {task.lastProcessedCount} items</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div className="bg-black/20 backdrop-blur-sm rounded-xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-white">Activity Logs</h2>
              <button
                onClick={fetchLogs}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
              >
                Refresh
              </button>
            </div>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {logs.length === 0 ? (
                <p className="text-gray-400">No logs available</p>
              ) : (
                logs.slice().reverse().map((log) => (
                  <div key={log.id} className="p-3 bg-white/5 rounded border border-white/10">
                    <div className="flex items-center justify-between">
                      <span className={`text-sm ${
                        log.type === 'error' ? 'text-red-400' :
                        log.type === 'success' ? 'text-green-400' :
                        'text-gray-300'
                      }`}>
                        {log.message}
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;