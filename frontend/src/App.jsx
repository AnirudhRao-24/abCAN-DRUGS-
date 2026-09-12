import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import * as $3Dmol from '3dmol';
import { Activity, Beaker, Upload, Settings, Maximize2, Layers } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

const getInterpretation = (ddg) => {
  if (ddg < -1.0) return "Highly likely affinity-improving candidate";
  if (ddg < -0.2) return "Potential affinity-improving candidate";
  if (ddg <= 0.2) return "Neutral / No significant effect";
  if (ddg <= 1.0) return "Potential destabilizing mutation";
  return "Highly likely destabilizing mutation";
};

function App() {
  const [appStarted, setAppStarted] = useState(false);
  const [pdbFile, setPdbFile] = useState('1a22.pdb');
  const [singlePos, setSinglePos] = useState('A:25');
  const [multiPos, setMultiPos] = useState('A:25, A:26');
  const [chainsStr, setChainsStr] = useState('A_B');
  const [results, setResults] = useState([]);
  const [selectedExplanation, setSelectedExplanation] = useState(null);
  const [mode, setMode] = useState('single');
  const [appView, setAppView] = useState('workspace'); // 'workspace' or 'screening'
  const [loading, setLoading] = useState(false);
  const [screenResults, setScreenResults] = useState([]);
  const viewerRef = useRef(null);
  const containerRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    // Initialize 3Dmol viewer when app starts
    if (appStarted && containerRef.current && !viewerRef.current) {
      viewerRef.current = $3Dmol.createViewer(containerRef.current, {
        backgroundColor: '#0b0f19',
      });
      loadPdb(pdbFile);
    }
  }, [appStarted]);

  const loadPdb = async (filename) => {
    if (!viewerRef.current) return;
    try {
      const response = await axios.get(`${API_BASE}/pdb/${filename}`, { responseType: 'text' });
      viewerRef.current.clear();
      viewerRef.current.addModel(response.data, "pdb");
      viewerRef.current.setStyle({}, { cartoon: { color: 'spectrum' } });
      viewerRef.current.zoomTo();
      viewerRef.current.render();
    } catch (e) {
      console.error("Failed to load PDB:", e);
    }
  };

  const highlightMutation = (mutationStr) => {
    if (!viewerRef.current) return;
    viewerRef.current.setStyle({}, { cartoon: { color: 'spectrum' } }); // reset
    
    // mutationStr is like FA25L or FA25L,DA26C
    const muts = mutationStr.split(',');
    for (let mut of muts) {
      const chain = mut[1];
      const pos = parseInt(mut.substring(2, mut.length - 1));
      
      // highlight specific residue
      viewerRef.current.setStyle({chain: chain, resi: pos}, {
        cartoon: { color: 'white' },
        stick: { radius: 0.2, colorscheme: 'greenCarbon' }
      });
      // sphere visualization
      viewerRef.current.addStyle({chain: chain, resi: pos}, { sphere: { radius: 0.8, color: '#10b981', opacity: 0.8 } });
      viewerRef.current.zoomTo({chain: chain, resi: pos});
    }
    viewerRef.current.render();
    
    // Fetch explanation
    try {
      axios.post(`${API_BASE}/explain`, {
        filename: pdbFile,
        mutation: mutationStr,
        chains: chainsStr
      }).then(res => {
        if (res.data && res.data.error) {
          alert("Explanation error: " + res.data.error);
          return;
        }
        if (res.data && res.data.contexts) {
          const r = results.find(r => r.mutation === mutationStr) || screenResults.find(r => r.mutation === mutationStr);
          setSelectedExplanation({
            mutationStr,
            ddg: r?.ddg,
            contexts: res.data.contexts
          });
        }
      });
    } catch (e) {
      console.error("Explanation fetch failed", e);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('chains', chainsStr);
    
    try {
      const res = await axios.post(`${API_BASE}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      if (res.data.error) {
        alert("Upload parsing error: " + res.data.error);
      } else {
        setPdbFile(res.data.filename);
        loadPdb(res.data.filename);
      }
    } catch (e) {
      console.error("Upload failed", e);
      alert("Upload failed: " + e.message);
    }
    setLoading(false);
  };

  const handleOptimize = async () => {
    setLoading(true);
    setResults([]);
    try {
      if (mode === 'single') {
        const res = await axios.post(`${API_BASE}/optimize/single`, {
          filename: pdbFile,
          position: singlePos
        });
        if (res.data.error) {
          alert("Optimization error: " + res.data.error);
        } else {
          setResults(res.data.results || []);
        }
      } else {
        const positions = multiPos.split(',').map(s => s.trim());
        const res = await axios.post(`${API_BASE}/optimize/multi`, {
          filename: pdbFile,
          positions: positions,
          top_k: 2
        });
        if (res.data.error) {
          alert("Optimization error: " + res.data.error);
        } else {
          setResults(res.data.results || []);
        }
      }
    } catch (e) {
      console.error("Optimization failed", e);
    }
    setLoading(false);
  };

  const handleScreen = async () => {
    setLoading(true);
    setScreenResults([]);
    try {
      const res = await axios.post(`${API_BASE}/optimize/screen`, {
        filename: pdbFile,
        chains: chainsStr
      });
      if (res.data.error) {
        alert("Screening error: " + res.data.error);
      } else {
        setScreenResults(res.data.results || []);
      }
    } catch (e) {
      console.error("Screening failed", e);
    }
    setLoading(false);
  };

  return (
    <div className="app-container">
      {/* Top Navigation Bar */}
      <div className="top-nav">
        <div className="nav-brand">abCAN-DRUGS</div>
        <div className="nav-links">
          <a onClick={() => setAppStarted(false)}>Project</a>
          <a className={appStarted && appView === 'workspace' ? 'active-nav' : ''} onClick={() => { setAppStarted(true); setAppView('workspace'); }}>Workspace</a>
          <a className={appStarted && appView === 'screening' ? 'active-nav' : ''} onClick={() => { setAppStarted(true); setAppView('screening'); }}>Mutation Screening</a>
          <a>Model</a>
          <a>Help</a>
        </div>
      </div>

      {!appStarted ? (
        <div className="landing-page">
          <div className="landing-title">abCAN-DRUGS</div>
          <div className="landing-subtitle">Antibody Mutation Affinity Analysis</div>
          <div className="landing-desc">
            Analyze antibody-antigen structures, predict mutation-induced affinity changes, 
            and identify promising mutation candidates using geometric deep learning.
          </div>
          <button className="landing-btn" onClick={() => setAppStarted(true)}>
            [ Analyze Structure ]
          </button>
        </div>
      ) : (
        <div className="main-workspace">
      
          {appView === 'screening' ? (
            <div className="sidebar" style={{ width: '400px' }}>
          <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
            <Layers size={22} color="#3b82f6" /> Mutation Screening
          </h2>
          <div className="glass-panel" style={{ marginBottom: '1rem' }}>
            <div style={{ color: '#9ca3af', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Structure: <span style={{ color: 'white' }}>{pdbFile}</span></div>
            <div style={{ color: '#9ca3af', fontSize: '0.9rem', marginBottom: '1rem' }}>Interface: <span style={{ color: 'white' }}>Antibody-Antigen</span></div>
            
            <button className="btn" onClick={handleScreen} disabled={loading}>
              {loading ? <Activity className="animate-spin" size={18}/> : <Settings size={18}/>}
              {loading ? 'Screening Interface...' : 'Run Interface Screen'}
            </button>
          </div>

          {screenResults.length > 0 && (
            <div className="glass-panel" style={{ flex: 1, overflow: 'auto' }}>
              <div style={{ marginBottom: '1rem', color: '#9ca3af', fontSize: '0.9rem' }}>Candidates: {screenResults.length}</div>
              <table className="results-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Mutation</th>
                    <th>ΔΔG</th>
                    <th>Position</th>
                  </tr>
                </thead>
                <tbody>
                  {screenResults.map((r, i) => (
                    <tr key={i} onClick={() => highlightMutation(r.mutation)} className={selectedExplanation?.mutationStr === r.mutation ? 'selected-row' : ''}>
                      <td>{i + 1}</td>
                      <td>{r.mutation}</td>
                      <td style={{ color: r.ddg < 0 ? '#10b981' : '#ef4444' }}>{r.ddg.toFixed(2)}</td>
                      <td style={{ fontSize: '0.8rem', color: '#9ca3af' }}>{r.position}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="sidebar">
          <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
            <Layers size={22} color="#3b82f6" /> Structure
          </h2>
          
          <div className="glass-panel">
            <div className="input-group">
              <label>Chains (Antibody_Antigen)</label>
              <input type="text" className="input-field" value={chainsStr} onChange={e => setChainsStr(e.target.value)} placeholder="e.g. A_B or HL_C" />
            </div>
            <div className="input-group">
              <label>PDB Structure</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input type="text" className="input-field" value={pdbFile} onChange={e => setPdbFile(e.target.value)} disabled />
                <input type="file" accept=".pdb" ref={fileInputRef} style={{ display: 'none' }} onChange={handleFileUpload} />
                <button className="btn" style={{ width: 'auto' }} onClick={() => fileInputRef.current?.click()} disabled={loading}>
                  <Upload size={16}/>
                </button>
              </div>
            </div>
            <button className="btn" onClick={() => loadPdb(pdbFile)}>Reload Viewer</button>
          </div>

          <div className="glass-panel">
            <h2>Optimization Target</h2>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <button className={`btn ${mode === 'single' ? '' : 'inactive'}`} style={{ opacity: mode === 'single' ? 1 : 0.5 }} onClick={() => setMode('single')}>Single</button>
              <button className={`btn ${mode === 'multi' ? '' : 'inactive'}`} style={{ opacity: mode === 'multi' ? 1 : 0.5 }} onClick={() => setMode('multi')}>Combinatorial</button>
            </div>
            
            {mode === 'single' ? (
              <div className="input-group">
                <label>Target Position (e.g. A:25)</label>
                <input type="text" className="input-field" value={singlePos} onChange={e => setSinglePos(e.target.value)} />
              </div>
            ) : (
              <div className="input-group">
                <label>Target Positions (comma separated)</label>
                <input type="text" className="input-field" value={multiPos} onChange={e => setMultiPos(e.target.value)} />
              </div>
            )}
            
            <button className="btn" onClick={handleOptimize} disabled={loading}>
              {loading ? <Activity className="animate-spin" size={18}/> : <Settings size={18}/>}
              {loading ? 'Optimizing...' : 'Run Optimization'}
            </button>
          </div>

          {results.length > 0 && (
            <div className="glass-panel" style={{ marginTop: '1rem', flex: 1, overflow: 'auto' }}>
              <h2>Results</h2>
              <table className="results-table">
                <thead>
                  <tr>
                    <th>Mutation</th>
                    <th>ΔΔG</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => (
                    <tr key={i} onClick={() => highlightMutation(r.mutation)} className={selectedExplanation?.mutationStr === r.mutation ? 'selected-row' : ''}>
                      <td>{r.mutation}</td>
                      <td style={{ color: r.ddg < 0 ? '#10b981' : '#ef4444' }}>{r.ddg.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      
      <div className="viewer-container" ref={containerRef}>
        {selectedExplanation && (
          <div className="explanation-overlay">
            <h2>Prediction Explanation</h2>
            {selectedExplanation.contexts.map((ctx, idx) => (
              <div key={idx} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.85rem' }}>
                  <div style={{ color: '#9ca3af' }}>Mutation</div>
                  <div style={{ fontWeight: 'bold' }}>{ctx.mutation}</div>
                  
                  <div style={{ color: '#9ca3af' }}>Predicted ΔΔG</div>
                  <div style={{ color: selectedExplanation.ddg < 0 ? '#10b981' : '#ef4444', fontWeight: 'bold' }}>
                    {selectedExplanation.ddg?.toFixed(2)}
                  </div>
                  
                  <div style={{ color: '#9ca3af' }}>Interpretation</div>
                  <div style={{ color: selectedExplanation.ddg < -0.2 ? '#10b981' : (selectedExplanation.ddg > 0.2 ? '#ef4444' : '#9ca3af') }}>
                    {getInterpretation(selectedExplanation.ddg)}
                  </div>
                  
                  <div style={{ color: '#9ca3af' }}>Position</div>
                  <div>{ctx.position}</div>
                  
                  <div style={{ color: '#9ca3af' }}>Interface residue</div>
                  <div>{ctx.is_interface ? 'Yes' : 'No'}</div>
                  
                  <div style={{ color: '#9ca3af' }}>Structural context</div>
                  <div>{ctx.is_interface ? 'Within antibody-antigen interface' : 'Outside interface'}</div>
                  
                  <div style={{ color: '#9ca3af' }}>Original residue</div>
                  <div>{ctx.original_residue}</div>
                  
                  <div style={{ color: '#9ca3af' }}>New residue</div>
                  <div>{ctx.new_residue}</div>
                  
                  <div style={{ color: '#9ca3af' }}>Distance to antigen</div>
                  <div>{ctx.distance_to_antigen !== null ? `${ctx.distance_to_antigen} Å` : 'N/A'}</div>
                  
                  <div style={{ color: '#9ca3af' }}>Interface neighborhood</div>
                  <div style={{ color: '#60a5fa' }}>{ctx.neighborhood.join(' ')}</div>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="viewer-overlay">
          <button className="overlay-btn active" onClick={() => {
            viewerRef.current?.setStyle({}, { cartoon: { color: 'spectrum' } });
            viewerRef.current.render();
          }}><Layers size={18}/> Cartoon</button>
          <button className="overlay-btn" onClick={() => viewerRef.current?.zoomTo()}><Maximize2 size={18}/> Reset View</button>
        </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
