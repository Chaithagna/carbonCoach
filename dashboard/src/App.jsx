import React, { useState, useEffect } from 'react';
import {
  Leaf,
  Send,
  Sparkles,
  TreePine,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  Car,
  Tv,
  Utensils,
  Trash2,
  Calendar,
  Layers,
  ArrowRight,
  ShieldCheck,
  PlusCircle,
  HelpCircle,
  BarChart3,
  Clock,
  X
} from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

export default function App() {
  // State
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I am Carbon Coach. Tell me what you did today (e.g. "I travelled 12 km by car and used the AC for 4 hours") and I will compute your verified emissions, check your budget, and suggest realistic greener alternatives!',
      tools: []
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [budgetStatus, setBudgetStatus] = useState(null);
  const [activities, setActivities] = useState([]);
  const [summary, setSummary] = useState(null);
  const [latestAlternative, setLatestAlternative] = useState(null);
  const [treeOffset, setTreeOffset] = useState(null);

  // Modals
  const [showLogModal, setShowLogModal] = useState(false);
  const [showLeaderboardModal, setShowLeaderboardModal] = useState(false);
  const [showFactorsModal, setShowFactorsModal] = useState(false);
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [leaderboardData, setLeaderboardData] = useState([]);

  // Log Form State
  const [logCategory, setLogCategory] = useState('travel');
  const [logMode, setLogMode] = useState('car_petrol');
  const [logQty, setLogQty] = useState('');
  const [previewKg, setPreviewKg] = useState(null);

  // Custom budget form
  const [customMonthly, setCustomMonthly] = useState(150);
  const [customSixMonth, setCustomSixMonth] = useState(900);

  // Initial load
  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [budgetRes, actRes, sumRes] = await Promise.all([
        fetch(`${API_BASE}/budget`).then(r => r.json()),
        fetch(`${API_BASE}/activities`).then(r => r.json()),
        fetch(`${API_BASE}/summary?period=month`).then(r => r.json())
      ]);
      setBudgetStatus(budgetRes);
      setActivities(actRes || []);
      setSummary(sumRes);

      if (budgetRes?.monthly?.excess_kg > 0) {
        const treeRes = await fetch(`${API_BASE}/tree-offset?excess_kg=${budgetRes.monthly.excess_kg}`).then(r => r.json());
        setTreeOffset(treeRes);
      } else {
        setTreeOffset(null);
      }
    } catch (err) {
      console.error('Error loading dashboard data:', err);
    }
  };

  // Chat message submit
  const handleSendMessage = async (textToSend) => {
    const text = textToSend || inputMessage;
    if (!text.trim() || loading) return;

    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, user_id: 'default_user' })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'The backend returned an error.';
        throw new Error(detail);
      }

      const assistantMsg = {
        role: 'assistant',
        content: data.reply || 'Calculation completed.',
        tools: (data.tool_results || []).map(t => t.tool)
      };

      setMessages(prev => [...prev, assistantMsg]);
      if (data.budget_status) setBudgetStatus(data.budget_status);
      if (data.alternatives && data.alternatives.length > 0) {
        setLatestAlternative(data.alternatives[0]);
      }

      await fetchDashboardData();
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Carbon Coach could not process that message: ${err.message || 'Check that server.py is running on port 8000.'}`
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Quick calculate preview for manual log modal
  useEffect(() => {
    const qty = parseFloat(logQty);
    if (!qty || qty <= 0) {
      setPreviewKg(null);
      return;
    }
    const factors = {
      walk: 0, cycle: 0, bus: 0.089, metro: 0.03, train: 0.04,
      two_wheeler: 0.05, auto_rickshaw: 0.10, car_petrol: 0.17, car_diesel: 0.17, car_electric: 0.05, flight_domestic: 0.15,
      ac: 1.5 * 0.71, fan: 0.07 * 0.71, light: 0.01 * 0.71, refrigerator: 0.15 * 0.71, laptop: 0.05 * 0.71, geyser: 2.0 * 0.71, washing_machine: 0.5 * 0.71,
      vegan: 0.4, veg: 0.7, egg: 1.0, fish: 1.4, chicken: 1.8, mutton: 5.5, beef: 6.5,
      mixed_landfill: 0.5, plastic: 2.0, food_waste: 0.8, paper: 1.0, recycled: 0.1
    };
    const f = factors[logMode] || 0;
    setPreviewKg((qty * f).toFixed(3));
  }, [logCategory, logMode, logQty]);

  // Submit manual activity log
  const handleManualLog = async (e) => {
    e.preventDefault();
    if (!previewKg) return;

    try {
      const details = `${logMode.replace('_', ' ')} (${logQty} ${logCategory === 'travel' ? 'km' : logCategory === 'appliance' ? 'hours' : logCategory === 'food' ? 'serving(s)' : 'kg'})`;
      await fetch(`${API_BASE}/activities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: logCategory,
          details,
          kg_co2e: parseFloat(previewKg)
        })
      });

      // Also get alternative
      const altRes = await fetch(`${API_BASE}/alternatives`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: logCategory,
          mode: logMode,
          quantity: parseFloat(logQty)
        })
      }).then(r => r.json());

      if (altRes?.status === 'success') {
        setLatestAlternative(altRes);
      }

      setShowLogModal(false);
      setLogQty('');
      fetchDashboardData();
    } catch (err) {
      alert('Failed to log activity.');
    }
  };

  // Update budget
  const handleSaveBudget = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API_BASE}/budget`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          monthly_kg: parseFloat(customMonthly),
          six_month_kg: parseFloat(customSixMonth)
        })
      });
      setShowBudgetModal(false);
      fetchDashboardData();
    } catch (err) {
      alert('Failed to update budget.');
    }
  };

  // Open leaderboard
  const handleOpenLeaderboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/leaderboard?group_type=hostel`).then(r => r.json());
      setLeaderboardData(res.leaderboard || []);
      setShowLeaderboardModal(true);
    } catch (err) {
      alert('Failed to load campus leaderboard.');
    }
  };

  const getCategoryIcon = (cat) => {
    switch (cat) {
      case 'travel': return <Car size={16} />;
      case 'appliance':
      case 'electricity': return <Tv size={16} />;
      case 'food': return <Utensils size={16} />;
      case 'waste': return <Trash2 size={16} />;
      default: return <Leaf size={16} />;
    }
  };

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="header">
        <div className="brand" onClick={() => fetchDashboardData()}>
          <div className="brand-icon-wrap">
            <Leaf size={22} />
          </div>
          <div>
            <div className="brand-title">
              Carbon Coach
              <span className="brand-badge">Google ADK</span>
            </div>
          </div>
        </div>

        <div className="header-actions">
          <button className="btn-secondary" onClick={() => setShowFactorsModal(true)}>
            <ShieldCheck size={16} /> Verified Sources
          </button>
          <button className="btn-secondary" onClick={handleOpenLeaderboard}>
            <BarChart3 size={16} /> Campus Mode
          </button>
          <button className="btn-secondary" onClick={() => setShowBudgetModal(true)}>
            <Layers size={16} /> Budget: {budgetStatus?.monthly?.budget_kg || 150} kg
          </button>
          <button className="btn-send" style={{ width: 'auto', padding: '0 1rem', gap: '0.4rem' }} onClick={() => setShowLogModal(true)}>
            <PlusCircle size={16} /> Log Activity
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <main className="main-content">
        {/* Left: Metrics & Visualizations */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* Tree Offset Plan Banner when Exceeded */}
          {budgetStatus?.monthly?.status === 'exceeded' && treeOffset && (
            <div className="tree-alert-banner">
              <div className="tree-alert-header">
                <div className="tree-alert-icon">
                  <TreePine size={24} />
                </div>
                <div>
                  <div className="tree-alert-title">
                    Monthly Carbon Limit Exceeded by {budgetStatus.monthly.excess_kg} kg CO2e
                  </div>
                  <div className="tree-alert-text">
                    You have crossed your monthly budget. In order to sequester the excess carbon, 
                    we have generated an actionable biological offset plan below.
                  </div>
                </div>
              </div>

              <div className="tree-plan-cards">
                <div className="tree-plan-item">
                  <div className="tree-count-num">{treeOffset.trees_needed}</div>
                  <div className="tree-plan-label">Trees for 1-Year Offset</div>
                </div>
                {treeOffset.timeline_options?.slice(1).map((opt, i) => (
                  <div key={i} className="tree-plan-item">
                    <div className="tree-count-num">{opt.trees_needed}</div>
                    <div className="tree-plan-label">Trees over {opt.years_to_offset} Years</div>
                  </div>
                ))}
              </div>

              <div style={{ fontSize: '0.8rem', color: '#fbcfe8', background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '8px' }}>
                <strong>Immediate Reduction Actions:</strong> 1. Switch short car trips under 5 km to Metro or Bus. 
                2. Set AC temperature to 24-26°C. <em>(Note: Trees require years of growth; cutting emissions at the source remains the top priority.)</em>
              </div>
            </div>
          )}

          {/* Budget Overview Cards */}
          <div className="glass-card">
            <div className="card-header">
              <div className="card-title-group">
                <Leaf size={20} color="#10b981" />
                <div>
                  <div className="card-title">Carbon Budget Status</div>
                  <div className="card-subtitle">Verified against India Baseline & Google ADK Tools</div>
                </div>
              </div>
              <div className={`status-pill ${budgetStatus?.status || 'ok'}`}>
                {budgetStatus?.status === 'exceeded' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
                {budgetStatus?.status || 'Active'}
              </div>
            </div>

            <div className="budgets-grid">
              {/* Monthly Budget Card */}
              <div className={`budget-metric-card ${budgetStatus?.monthly?.status || 'ok'}`}>
                <div className="budget-card-top">
                  <span className="budget-label">Calendar Month</span>
                  <span className={`status-pill ${budgetStatus?.monthly?.status || 'ok'}`} style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}>
                    {budgetStatus?.monthly?.status || 'OK'}
                  </span>
                </div>
                <div className="budget-value-row">
                  <span className="budget-value-large">{budgetStatus?.monthly?.used_kg ?? 0}</span>
                  <span className="budget-value-limit">/ {budgetStatus?.monthly?.budget_kg || 150} kg</span>
                </div>
                <div className="progress-bar-track">
                  <div 
                    className={`progress-bar-fill ${budgetStatus?.monthly?.status || 'ok'}`}
                    style={{ width: `${Math.min(100, budgetStatus?.monthly?.percent_used || 0)}%` }}
                  />
                </div>
                <div className="budget-meta-row">
                  <span>{budgetStatus?.monthly?.percent_used ?? 0}% consumed</span>
                  <span>{budgetStatus?.monthly?.remaining_kg ?? 150} kg left</span>
                </div>
              </div>

              {/* 6-Month Rolling Budget Card */}
              <div className={`budget-metric-card ${budgetStatus?.six_months?.status || 'ok'}`}>
                <div className="budget-card-top">
                  <span className="budget-label">Rolling 6 Months</span>
                  <span className={`status-pill ${budgetStatus?.six_months?.status || 'ok'}`} style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}>
                    {budgetStatus?.six_months?.status || 'OK'}
                  </span>
                </div>
                <div className="budget-value-row">
                  <span className="budget-value-large">{budgetStatus?.six_months?.used_kg ?? 0}</span>
                  <span className="budget-value-limit">/ {budgetStatus?.six_months?.budget_kg || 900} kg</span>
                </div>
                <div className="progress-bar-track">
                  <div 
                    className={`progress-bar-fill ${budgetStatus?.six_months?.status || 'ok'}`}
                    style={{ width: `${Math.min(100, budgetStatus?.six_months?.percent_used || 0)}%` }}
                  />
                </div>
                <div className="budget-meta-row">
                  <span>{budgetStatus?.six_months?.percent_used ?? 0}% consumed</span>
                  <span>{budgetStatus?.six_months?.remaining_kg ?? 900} kg left</span>
                </div>
              </div>
            </div>

            {/* Category Breakdown */}
            <div style={{ marginTop: '1.25rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                This Month's Category Breakdown
              </div>
              <div className="category-grid">
                {['travel', 'appliance', 'food', 'waste'].map(cat => {
                  const data = summary?.category_breakdown?.[cat] || { kg_co2e: 0, percentage: 0 };
                  return (
                    <div key={cat} className="category-chip">
                      <div className="category-chip-title">
                        {getCategoryIcon(cat)} {cat}
                      </div>
                      <div className="category-chip-kg">{data.kg_co2e} kg</div>
                      <div className="category-chip-pct">{data.percentage}% of total</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Greener Alternatives Spotlight */}
          {latestAlternative && (
            <div className="glass-card">
              <div className="card-header">
                <div className="card-title-group">
                  <TrendingDown size={20} color="#34d399" />
                  <div>
                    <div className="card-title">Greener & Compatible Alternatives</div>
                    <div className="card-subtitle">
                      Evaluated for: {latestAlternative.mode?.replace('_', ' ')} ({latestAlternative.quantity} units, {latestAlternative.current_kg} kg CO2e)
                    </div>
                  </div>
                </div>
              </div>

              {latestAlternative.already_optimal ? (
                <div style={{ padding: '1rem', background: 'rgba(16,185,129,0.1)', borderRadius: '12px', border: '1px solid rgba(16,185,129,0.2)' }}>
                  <CheckCircle2 color="#34d399" size={20} style={{ display: 'inline', marginRight: '0.5rem' }} />
                  {latestAlternative.message}
                </div>
              ) : (
                <div className="alternatives-container">
                  {latestAlternative.alternatives?.slice(0, 3).map((alt, idx) => (
                    <div key={idx} className="alt-card">
                      <div className="alt-info">
                        <div className="alt-name">{alt.name}</div>
                        <div className="alt-note">{alt.note}</div>
                      </div>
                      <div className="alt-stats">
                        <span className="alt-saving-badge">
                          Save {alt.saving_kg} kg ({alt.saving_percent}%)
                        </span>
                        <span className={`ease-badge ${alt.ease.replace(' ', '-')}`}>
                          {alt.ease}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Activity History */}
          <div className="glass-card">
            <div className="card-header">
              <div className="card-title-group">
                <Clock size={20} color="#38bdf8" />
                <div>
                  <div className="card-title">Logged Activities History</div>
                  <div className="card-subtitle">Persisted in SQLite for rolling 6-month tracking</div>
                </div>
              </div>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {activities.length} total entries
              </span>
            </div>

            <div className="activity-list">
              {activities.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No activities logged yet. Type a message in the chat or click "Log Activity"!
                </div>
              ) : (
                activities.slice(0, 10).map((act) => (
                  <div key={act.id} className="activity-row">
                    <div className="activity-main">
                      <div className="cat-icon-badge">
                        {getCategoryIcon(act.category)}
                      </div>
                      <div>
                        <div className="activity-details">{act.details}</div>
                        <div className="activity-time">
                          {new Date(act.timestamp).toLocaleDateString()} {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                    </div>
                    <div className="activity-kg">
                      {act.kg_co2e} kg
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>

        {/* Right: Conversational AI Agent Chat */}
        <div className="glass-card chat-panel">
          <div className="card-header" style={{ marginBottom: '0.5rem' }}>
            <div className="card-title-group">
              <Sparkles size={18} color="#10b981" />
              <div>
                <div className="card-title" style={{ fontSize: '1rem' }}>Chat with Carbon Coach</div>
                <div className="card-subtitle" style={{ fontSize: '0.75rem' }}>Google ADK • LLM never invents numbers</div>
              </div>
            </div>
          </div>

          {/* Quick Example Chips */}
          <div className="chat-chips">
            <button className="chip-btn" onClick={() => handleSendMessage('I travelled 12 km by car and used the AC for 4 hours.')}>
              🚗 Car 12km + AC 4h
            </button>
            <button className="chip-btn" onClick={() => handleSendMessage('I travelled 10 km by bus today.')}>
              🚌 Bus 10km
            </button>
            <button className="chip-btn" onClick={() => handleSendMessage('How did I do this week?')}>
              📊 Weekly Summary
            </button>
            <button className="chip-btn" onClick={() => handleSendMessage('आज मैंने 10 किमी बस की यात्रा की।')}>
              🇮🇳 हिंदी (Hindi)
            </button>
            <button className="chip-btn" onClick={() => handleSendMessage('నేను ఈరోజు 15 కిలోమీటర్లు మెట్రోలో ప్రయాణించాను.')}>
              🇮🇳 తెలుగు (Telugu)
            </button>
          </div>

          {/* Message Stream */}
          <div className="chat-messages">
            {messages.map((m, idx) => (
              <div key={idx} className={`chat-bubble ${m.role}`}>
                {m.content}
                {m.tools && m.tools.length > 0 && (
                  <div className="tool-badge-row">
                    {m.tools.map((tName, tIdx) => (
                      <span key={tIdx} className="tool-badge">
                        ⚡ {tName}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="chat-bubble assistant" style={{ fontStyle: 'italic', color: 'var(--emerald-400)' }}>
                Running Google ADK calculation tools...
              </div>
            )}
          </div>

          {/* Chat Form */}
          <form className="chat-input-form" onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}>
            <input
              type="text"
              className="chat-input"
              placeholder="e.g. 'Took metro 15 km and ate a chicken meal'"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="btn-send" disabled={loading || !inputMessage.trim()}>
              <Send size={18} />
            </button>
          </form>
        </div>
      </main>

      {/* Modal 1: Quick Log Activity */}
      {showLogModal && (
        <div className="modal-overlay" onClick={() => setShowLogModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="card-header">
              <div className="card-title">Log Daily Activity</div>
              <X size={20} style={{ cursor: 'pointer' }} onClick={() => setShowLogModal(false)} />
            </div>

            <form onSubmit={handleManualLog}>
              <div className="form-group">
                <label className="form-label">Category</label>
                <select className="form-select" value={logCategory} onChange={e => {
                  setLogCategory(e.target.value);
                  if (e.target.value === 'travel') setLogMode('car_petrol');
                  if (e.target.value === 'appliance') setLogMode('ac');
                  if (e.target.value === 'food') setLogMode('chicken');
                  if (e.target.value === 'waste') setLogMode('plastic');
                }}>
                  <option value="travel">Transport & Travel</option>
                  <option value="appliance">Appliance / Electricity</option>
                  <option value="food">Diet / Food</option>
                  <option value="waste">Waste Disposal</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Activity Mode</label>
                <select className="form-select" value={logMode} onChange={e => setLogMode(e.target.value)}>
                  {logCategory === 'travel' && (
                    <>
                      <option value="walk">Walk (0 kg/km)</option>
                      <option value="cycle">Cycle (0 kg/km)</option>
                      <option value="bus">Public Bus (0.089 kg/km)</option>
                      <option value="metro">Metro (0.030 kg/km)</option>
                      <option value="train">Train (0.040 kg/km)</option>
                      <option value="two_wheeler">Two-Wheeler (0.050 kg/km)</option>
                      <option value="auto_rickshaw">Auto Rickshaw (0.100 kg/km)</option>
                      <option value="car_petrol">Petrol Car (0.170 kg/km)</option>
                      <option value="car_diesel">Diesel Car (0.170 kg/km)</option>
                      <option value="car_electric">Electric Car (0.050 kg/km)</option>
                      <option value="flight_domestic">Domestic Flight (0.150 kg/km)</option>
                    </>
                  )}
                  {logCategory === 'appliance' && (
                    <>
                      <option value="ac">Air Conditioner (1.5 kW)</option>
                      <option value="fan">Ceiling Fan (0.07 kW)</option>
                      <option value="light">LED Light (0.01 kW)</option>
                      <option value="refrigerator">Refrigerator (0.15 kW)</option>
                      <option value="laptop">Laptop (0.05 kW)</option>
                      <option value="geyser">Water Geyser (2.0 kW)</option>
                      <option value="washing_machine">Washing Machine (0.5 kW)</option>
                    </>
                  )}
                  {logCategory === 'food' && (
                    <>
                      <option value="vegan">Vegan Meal (0.4 kg)</option>
                      <option value="veg">Vegetarian Meal (0.7 kg)</option>
                      <option value="egg">Egg Meal (1.0 kg)</option>
                      <option value="fish">Fish Meal (1.4 kg)</option>
                      <option value="chicken">Chicken Meal (1.8 kg)</option>
                      <option value="mutton">Mutton Meal (5.5 kg)</option>
                      <option value="beef">Beef Meal (6.5 kg)</option>
                    </>
                  )}
                  {logCategory === 'waste' && (
                    <>
                      <option value="mixed_landfill">Mixed Landfill (0.5 kg/kg)</option>
                      <option value="plastic">Single-use Plastic (2.0 kg/kg)</option>
                      <option value="food_waste">Food Waste to Dump (0.8 kg/kg)</option>
                      <option value="paper">Paper (1.0 kg/kg)</option>
                      <option value="recycled">Recycled Waste (0.1 kg/kg)</option>
                    </>
                  )}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Quantity ({logCategory === 'travel' ? 'km' : logCategory === 'appliance' ? 'hours' : logCategory === 'food' ? 'servings' : 'kg'})
                </label>
                <input
                  type="number"
                  step="any"
                  min="0.1"
                  required
                  className="form-input"
                  placeholder="e.g. 12"
                  value={logQty}
                  onChange={e => setLogQty(e.target.value)}
                />
              </div>

              {previewKg !== null && (
                <div style={{ background: 'rgba(16,185,129,0.15)', padding: '0.85rem', borderRadius: '8px', marginBottom: '1.25rem', border: '1px solid var(--border-glow)' }}>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Calculated Output:</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--emerald-400)' }}>
                    {previewKg} kg CO2e
                  </div>
                </div>
              )}

              <button type="submit" className="btn-send" style={{ width: '100%', height: '44px', fontWeight: 600 }}>
                Log into Verified History
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Campus Mode Leaderboard */}
      {showLeaderboardModal && (
        <div className="modal-overlay" onClick={() => setShowLeaderboardModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="card-header">
              <div className="card-title">Campus Mode: Hostel Leaderboard</div>
              <X size={20} style={{ cursor: 'pointer' }} onClick={() => setShowLeaderboardModal(false)} />
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Hostels ranked by lowest average kg CO2e per student:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {leaderboardData.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No campus activity records logged yet.
                </div>
              ) : (
                leaderboardData.map((item, idx) => (
                  <div key={idx} className="activity-row">
                    <div>
                      <div style={{ fontWeight: 700 }}>#{item.rank} {item.group_name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{item.member_count} active members</div>
                    </div>
                    <div style={{ fontWeight: 700, color: 'var(--emerald-400)' }}>
                      {item.avg_kg_per_person} kg / person
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal 3: Factors & Sources Transparency */}
      {showFactorsModal && (
        <div className="modal-overlay" onClick={() => setShowFactorsModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '650px' }}>
            <div className="card-header">
              <div className="card-title">Verified Emission Factors & Sources</div>
              <X size={20} style={{ cursor: 'pointer' }} onClick={() => setShowFactorsModal(false)} />
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <p style={{ marginBottom: '0.75rem' }}>
                <strong>India Grid Electricity:</strong> 0.71 kg CO2e/kWh (Central Electricity Authority - CEA CO2 Baseline Database for Indian Power Sector).
              </p>
              <p style={{ marginBottom: '0.75rem' }}>
                <strong>Transport:</strong> Bus (0.089 kg/km), Metro (0.030 kg/km), Train (0.040 kg/km), Car Petrol (0.170 kg/km), Two-Wheeler (0.050 kg/km). <em>Source: DEFRA / ARAI India transit conversions.</em>
              </p>
              <p style={{ marginBottom: '0.75rem' }}>
                <strong>Appliances:</strong> 1.5 Ton AC (1.5 kW), Ceiling Fan (0.07 kW), Geyser (2.0 kW). <em>Source: BEE India appliance energy standards.</em>
              </p>
              <p style={{ marginBottom: '0.75rem' }}>
                <strong>Food:</strong> Vegan (0.4 kg/meal), Veg (0.7 kg/meal), Chicken (1.8 kg/meal), Mutton (5.5 kg/meal). <em>Source: Poore & Nemecek (Science 2018) / Our World in Data.</em>
              </p>
              <p style={{ marginBottom: '0.75rem' }}>
                <strong>Tree Offset:</strong> 21 kg CO2 absorbed per mature tree annually. <em>Source: European Environment Agency (EEA) / Arbor Day Foundation.</em>
              </p>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '0.5rem' }}>
                *All values are empirical estimates calibrated to Indian per-capita averages (~2 tCO2e/year).
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Modal 4: Customize Budget */}
      {showBudgetModal && (
        <div className="modal-overlay" onClick={() => setShowBudgetModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="card-header">
              <div className="card-title">Configure Carbon Budgets</div>
              <X size={20} style={{ cursor: 'pointer' }} onClick={() => setShowBudgetModal(false)} />
            </div>
            <form onSubmit={handleSaveBudget}>
              <div className="form-group">
                <label className="form-label">Monthly Budget (kg CO2e)</label>
                <input
                  type="number"
                  min="10"
                  step="5"
                  required
                  className="form-input"
                  value={customMonthly}
                  onChange={e => setCustomMonthly(e.target.value)}
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Default: 150 kg (approx Indian per-capita monthly baseline)</span>
              </div>
              <div className="form-group">
                <label className="form-label">Six-Month Budget (kg CO2e)</label>
                <input
                  type="number"
                  min="50"
                  step="25"
                  required
                  className="form-input"
                  value={customSixMonth}
                  onChange={e => setCustomSixMonth(e.target.value)}
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Default: 900 kg</span>
              </div>
              <button type="submit" className="btn-send" style={{ width: '100%', height: '44px', fontWeight: 600 }}>
                Save Budget
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
