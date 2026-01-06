import React, { useState, useEffect, useRef } from 'react';
import { Download, AlertCircle, CheckCircle, Server, Terminal, RotateCcw, Play, Wifi } from 'lucide-react';

export default function App() {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState('idle'); // idle, connecting, downloading, processing, complete, error
  const [progress, setProgress] = useState(0);
  const [currentAction, setCurrentAction] = useState('Idle'); // New state for granular status text
  const [logs, setLogs] = useState([]);
  const [simulateStuck, setSimulateStuck] = useState(false);
  
  const logContainerRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { time: timestamp, message, type }]);
  };

  const handleDownload = () => {
    if (!url) {
      addLog('Please enter a valid URL first.', 'error');
      return;
    }

    setStatus('connecting');
    setProgress(0);
    setCurrentAction('Initializing connection...');
    setLogs([]);
    addLog(`Initializing download for: ${url}`);
    
    // Simulation Logic
    setTimeout(() => {
      startDownloadSequence();
    }, 1000);
  };

  const startDownloadSequence = () => {
    setStatus('downloading');
    setCurrentAction('Connected. Requesting metadata...');
    addLog('Connected to backend server.', 'success');
    addLog('Requesting video metadata...');

    let currentProgress = 0;
    const interval = setInterval(() => {
      
      // LOGIC FOR STUCK SIMULATION
      if (simulateStuck && currentProgress >= 45) {
        clearInterval(interval);
        setCurrentAction('Waiting for server response...');
        addLog('WARNING: Server response delayed...', 'warning');
        setTimeout(() => {
          setStatus('error');
          setCurrentAction('Connection Timed Out');
          addLog('ERROR: Gateway Timeout (504). Server took too long to respond.', 'error');
          addLog('Troubleshooting: Check server bandwidth or increase timeout limits.', 'info');
        }, 3000);
        return;
      }

      // NORMAL DOWNLOAD SIMULATION
      currentProgress += Math.floor(Math.random() * 5) + 1;
      
      if (currentProgress <= 50) {
        // Phase 1: Downloading to Server (0-50% Global)
        // Map 0-50 global to 0-100 local for display logic if needed
        
        if (currentProgress > 0 && currentProgress < 10) setCurrentAction('Allocating server resources...');
        if (currentProgress === 10) {
           const msg = 'Stream detected: 1080p/MP4';
           addLog(msg);
           setCurrentAction(msg);
        }
        if (currentProgress >= 15 && currentProgress < 25) {
           const msg = 'Downloading segment 1/4...';
           if (currentAction !== msg) { addLog(msg); setCurrentAction(msg); }
        }
        if (currentProgress >= 25 && currentProgress < 35) {
           const msg = 'Downloading segment 2/4...';
           if (currentAction !== msg) { addLog(msg); setCurrentAction(msg); }
        }
        if (currentProgress >= 35 && currentProgress < 45) {
           const msg = 'Downloading segment 3/4...';
           if (currentAction !== msg) { addLog(msg); setCurrentAction(msg); }
        }
        if (currentProgress >= 45) {
           const msg = 'Downloading segment 4/4...';
           if (currentAction !== msg) { addLog(msg); setCurrentAction(msg); }
        }

      } else if (currentProgress <= 90) {
        // Phase 2: Processing (51-90% Global)
        if (status !== 'processing' && currentProgress > 50) {
          setStatus('processing');
          const msg = 'Segments acquired. Merging files...';
          addLog(msg, 'info');
          setCurrentAction(msg);
        }
        if (currentProgress >= 60 && currentProgress < 70) {
           const msg = 'Transcoding audio stream (AAC)...';
           if (currentAction !== msg) { addLog(msg); setCurrentAction(msg); }
        }
        if (currentProgress >= 70 && currentProgress < 80) {
           const msg = 'Encoding video container...';
           if (currentAction !== msg) { addLog(msg); setCurrentAction(msg); }
        }
        if (currentProgress >= 80) {
           const msg = 'Finalizing file structure...';
           if (currentAction !== msg) { addLog(msg); setCurrentAction(msg); }
        }
      } else {
        // Phase 3: Complete
        clearInterval(interval);
        setProgress(100);
        setStatus('complete');
        setCurrentAction('Ready for download');
        addLog('Download ready. Sending to client.', 'success');
        return;
      }

      setProgress(Math.min(currentProgress, 99));
    }, 200);
  };

  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setCurrentAction('Idle');
    setLogs([]);
    setUrl('');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans p-4 md:p-8 flex items-center justify-center">
      <div className="max-w-3xl w-full bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
        
        {/* Header */}
        <div className="bg-slate-800/50 p-6 border-b border-slate-700 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Download className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Server-Side Downloader</h1>
              <p className="text-xs text-slate-400">Simulate backend video processing states</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono bg-black/30 px-3 py-1 rounded-full border border-slate-700">
            <div className={`w-2 h-2 rounded-full ${status === 'idle' ? 'bg-slate-500' : 'bg-green-500 animate-pulse'}`}></div>
            {status === 'idle' ? 'IDLE' : 'ACTIVE'}
          </div>
        </div>

        <div className="p-6 space-y-8">
          
          {/* Input Section */}
          <div className="space-y-4">
            <label className="block text-sm font-medium text-slate-400">Target Video URL</label>
            <div className="flex gap-2">
              <input 
                type="text" 
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/video/watch?v=..." 
                className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600"
                disabled={status !== 'idle'}
              />
              {status === 'idle' ? (
                <button 
                  onClick={handleDownload}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Play className="w-4 h-4" /> Start
                </button>
              ) : (
                <button 
                  onClick={reset}
                  className="bg-slate-700 hover:bg-slate-600 text-white px-6 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  <RotateCcw className="w-4 h-4" /> Reset
                </button>
              )}
            </div>
            
            {/* Simulation Controls */}
            {status === 'idle' && (
              <div className="flex items-center gap-2">
                <input 
                  type="checkbox" 
                  id="simulateStuck" 
                  checked={simulateStuck} 
                  onChange={(e) => setSimulateStuck(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-offset-slate-900" 
                />
                <label htmlFor="simulateStuck" className="text-xs text-amber-400 select-none cursor-pointer">
                  Simulate "Stuck at 45%" Error (Replicates your issue)
                </label>
              </div>
            )}
          </div>

          {/* Status Display */}
          {status !== 'idle' && (
            <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
              
              {/* Progress Bar & Current Action */}
              <div className="bg-slate-800/30 rounded-xl p-4 border border-slate-700/50 space-y-3">
                <div className="flex justify-between items-end">
                  <div className="space-y-1">
                    <div className="text-xs uppercase tracking-wider font-bold text-slate-500">Current Status</div>
                    <div className={`text-sm font-medium font-mono ${status === 'error' ? 'text-red-400' : 'text-blue-400'}`}>
                       {status === 'error' ? 'Failed' : currentAction}
                    </div>
                  </div>
                  <div className="text-2xl font-bold text-white">{progress}%</div>
                </div>

                <div className="h-3 bg-slate-800 rounded-full overflow-hidden border border-slate-700">
                  <div 
                    className={`h-full transition-all duration-300 ease-out relative ${
                      status === 'error' ? 'bg-red-500' : 
                      status === 'complete' ? 'bg-green-500' : 
                      'bg-gradient-to-r from-blue-600 to-cyan-400'
                    }`} 
                    style={{ width: `${progress}%` }}
                  >
                    {/* Striped Animation overlay */}
                    {status !== 'error' && status !== 'complete' && (
                      <div className="absolute inset-0 bg-white/20" style={{
                        backgroundImage: 'linear-gradient(45deg,rgba(255,255,255,.15) 25%,transparent 25%,transparent 50%,rgba(255,255,255,.15) 50%,rgba(255,255,255,.15) 75%,transparent 75%,transparent)',
                        backgroundSize: '1rem 1rem',
                      }}></div>
                    )}
                  </div>
                </div>
              </div>

              {/* Steps Visualizer */}
              <div className="grid grid-cols-3 gap-4">
                <StepCard 
                  icon={Wifi} 
                  label="Connect" 
                  active={status === 'connecting' || progress > 0} 
                  completed={progress > 10}
                  error={status === 'error' && progress < 10}
                />
                <StepCard 
                  icon={Server} 
                  label="Download" 
                  active={status === 'downloading'} 
                  completed={progress > 50}
                  error={status === 'error' && progress <= 50}
                  // Calculate local percentage for download phase (0-50 global = 0-100 local)
                  details={status === 'downloading' ? `${Math.min(100, Math.floor((progress / 50) * 100))}%` : null}
                />
                <StepCard 
                  icon={CheckCircle} 
                  label="Process" 
                  active={status === 'processing'} 
                  completed={status === 'complete'}
                  error={status === 'error' && progress > 50}
                   // Calculate local percentage for processing phase (50-90 global = 0-100 local approximately)
                  details={status === 'processing' ? `${Math.min(100, Math.floor(((progress - 50) / 40) * 100))}%` : null}
                />
              </div>

              {/* Terminal Logs */}
              <div className="bg-black rounded-lg border border-slate-800 overflow-hidden font-mono text-xs">
                <div className="bg-slate-900/50 px-4 py-2 border-b border-slate-800 flex items-center gap-2 text-slate-500">
                  <Terminal className="w-3 h-3" />
                  <span>server_logs.log</span>
                </div>
                <div ref={logContainerRef} className="p-4 h-48 overflow-y-auto space-y-1">
                  {logs.map((log, i) => (
                    <div key={i} className="flex gap-3">
                      <span className="text-slate-600 shrink-0">[{log.time}]</span>
                      <span className={`${
                        log.type === 'error' ? 'text-red-400' : 
                        log.type === 'success' ? 'text-green-400' : 
                        log.type === 'warning' ? 'text-amber-400' : 
                        'text-slate-300'
                      }`}>
                        {log.type === 'error' && '✖ '}
                        {log.type === 'success' && '✓ '}
                        {log.type === 'warning' && '⚠ '}
                        {log.message}
                      </span>
                    </div>
                  ))}
                  {status === 'downloading' && (
                    <div className="animate-pulse text-blue-400">_</div>
                  )}
                </div>
              </div>

              {/* Result Actions */}
              {status === 'complete' && (
                <div className="flex justify-center pt-2">
                   <button className="bg-green-600 hover:bg-green-500 text-white px-8 py-3 rounded-xl font-bold shadow-lg shadow-green-900/20 transition-all transform hover:scale-105 flex items-center gap-2">
                     <Download className="w-5 h-5" /> Save File to Disk
                   </button>
                </div>
              )}

              {status === 'error' && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-400 mt-0.5" />
                  <div>
                    <h3 className="text-red-400 font-semibold text-sm">Download Failed</h3>
                    <p className="text-red-400/80 text-xs mt-1">The server connection timed out while downloading the segment. This usually happens when the source video is too large or the server bandwidth is throttled.</p>
                  </div>
                </div>
              )}

            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StepCard({ icon: Icon, label, active, completed, error, details }) {
  return (
    <div className={`
      relative p-4 rounded-xl border flex flex-col items-center gap-2 transition-all duration-300
      ${error ? 'bg-red-500/5 border-red-500/30' : 
        completed ? 'bg-green-500/5 border-green-500/30' : 
        active ? 'bg-blue-500/5 border-blue-500/30 scale-105 shadow-lg shadow-blue-900/20' : 
        'bg-slate-900 border-slate-800 opacity-50'}
    `}>
      <div className={`
        p-2 rounded-lg 
        ${error ? 'bg-red-500/20 text-red-400' :
          completed ? 'bg-green-500/20 text-green-400' : 
          active ? 'bg-blue-500/20 text-blue-400' : 
          'bg-slate-800 text-slate-500'}
      `}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex flex-col items-center">
        <span className={`
          text-xs font-semibold
          ${error ? 'text-red-400' :
            completed ? 'text-green-400' : 
            active ? 'text-blue-300' : 
            'text-slate-500'}
        `}>
          {label}
        </span>
        {active && details && (
          <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 mt-1 rounded-full animate-pulse">
            {details}
          </span>
        )}
      </div>
      
      {/* Connector Line (visual only) */}
      {completed && (
        <div className="absolute top-1/2 -right-4 w-8 h-[2px] bg-green-500/30 hidden md:block"></div>
      )}
    </div>
  );
}
