import React, { useRef, useState } from 'react'
import axios from 'axios'
import Plotly from 'plotly.js-dist-min'

export default function App() {
  const [horizon, setHorizon] = useState(12)
  const [series, setSeries] = useState([])
  const [loading, setLoading] = useState(false)
  const [lastForecast, setLastForecast] = useState(null)
  const [fileName, setFileName] = useState('')
  const [rowCount, setRowCount] = useState(0)
  const [status, setStatus] = useState('Upload a CSV file and select horizon to forecast.')
  const [error, setError] = useState('')
  const plotRef = useRef(null)

  // Robust CSV parsing: detect numeric column, skip header rows
  function parseCSV(text) {
    const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
    if (!lines.length) return []
    const rows = lines.map(l => l.split(/,|;|\t/).map(c => c.trim()))
    // If header: try to detect non-numeric in first row
    let start = 0
    if (rows[0].some(v => isNaN(parseFloat(v)))) start = 1

    // Find the first column index that parses to numbers for most rows
    const colCount = rows[0].length
    const scores = Array(colCount).fill(0)
    for (let c = 0; c < colCount; c++) {
      for (let r = start; r < rows.length; r++) {
        if (!rows[r][c]) continue
        if (!Number.isNaN(parseFloat(rows[r][c]))) scores[c] += 1
      }
    }
    const bestCol = scores.indexOf(Math.max(...scores))
    const vals = []
    for (let r = start; r < rows.length; r++) {
      const v = parseFloat(rows[r][bestCol])
      if (!Number.isNaN(v)) vals.push(v)
    }
    return vals
  }

  async function handleFile(e) {
    const f = e.target.files[0]
    if (!f) return
    setError('')
    setStatus('Parsing file...')
    const txt = await f.text()
    const vals = parseCSV(txt)
    setSeries(vals)
    setFileName(f.name)
    setRowCount(vals.length)
    setStatus(vals.length
      ? `Loaded ${vals.length} numeric values from ${f.name}`
      : `No numeric values found in ${f.name}. Please upload a CSV with a numeric value column.`)
  }

  function downloadObjectAsJson(exportObj, exportName) {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportObj, null, 2))
    const dlAnchor = document.createElement('a')
    dlAnchor.setAttribute('href', dataStr)
    dlAnchor.setAttribute('download', exportName + '.json')
    dlAnchor.click()
  }

  function downloadForecastCSV(point, quantiles) {
    // quantiles: [T][Q] - pick sensible lower/upper (e.g., Q20 and Q80 if available)
    const qLowerIdx = Math.min(1, quantiles[0].length - 1)
    const qUpperIdx = Math.max(quantiles[0].length - 2, 0)
    const rows = [['horizon_index','point','lower','upper']]
    for (let i = 0; i < point.length; i++) {
      const lower = quantiles[i][qLowerIdx]
      const upper = quantiles[i][qUpperIdx]
      rows.push([i+1, point[i], lower, upper])
    }
    const csv = rows.map(r => r.join(',')).join('\n')
    const dataStr = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv)
    const a = document.createElement('a')
    a.setAttribute('href', dataStr)
    a.setAttribute('download', 'forecast.csv')
    a.click()
  }

  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api'

  async function runForecast() {
    if (!series.length) {
      setError('Upload a CSV with a numeric column first.')
      setStatus('No data to forecast.')
      return
    }
    setError('')
    setLoading(true)
    setStatus('Requesting forecast...')
    try {
      const resp = await axios.post(`${apiBase}/forecast`, {
        horizon: parseInt(horizon, 10),
        series: series,
      })
      const { point, quantiles } = resp.data
      setLastForecast({ point, quantiles })

      const x = Array.from({ length: point.length }, (_, i) => i + 1)
      const lower = quantiles.map(row => row[1] ?? row[0])
      const upper = quantiles.map(row => row[row.length - 2] ?? row[row.length - 1])

      const tracePoint = {
        x,
        y: point,
        mode: 'lines+markers',
        name: 'Forecast',
        marker: { color: '#1f77b4', size: 6 },
        line: { color: '#1f77b4', width: 2 },
      }
      const traceUpper = {
        x,
        y: upper,
        mode: 'lines',
        name: 'Upper bound',
        line: { color: 'rgba(31,119,180,0.3)' },
      }
      const traceLower = {
        x,
        y: lower,
        mode: 'lines',
        name: 'Lower bound',
        fill: 'tonexty',
        fillcolor: 'rgba(31,119,180,0.12)',
        line: { color: 'rgba(31,119,180,0.3)' },
      }

      Plotly.newPlot(plotRef.current, [traceLower, traceUpper, tracePoint], {
        margin: { t: 36, r: 18, l: 48, b: 40 },
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#f9fbff',
        xaxis: { title: 'Forecast step', showgrid: true, gridcolor: '#e8ebf3' },
        yaxis: { title: 'Value', zeroline: false, gridcolor: '#e8ebf3' },
        legend: { orientation: 'h', y: 1.12 },
      })
      setStatus(`Forecast completed: ${point.length} steps returned.`)
    } catch (err) {
      console.error(err)
      setError('Forecast failed: ' + (err.response?.data?.detail || err.message))
      setStatus('Forecast request failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <header className="hero">
        <div>
          <h1>TimesFM Forecast UI</h1>
          <p>Upload a numeric CSV with a value column, choose a horizon, and see the forecast with uncertainty bands.</p>
        </div>
        <div className="status-box">
          <strong>Status:</strong> {status}
          {error ? <div className="error">{error}</div> : null}
        </div>
      </header>

      <section className="controls-grid">
        <div className="card">
          <h2>Input</h2>
          <label className="file-upload">
            <span>Upload CSV</span>
            <input type="file" accept=".csv,.txt" onChange={handleFile} />
          </label>
          <p className="meta">File: <strong>{fileName || 'None'}</strong></p>
          <p className="meta">Values detected: <strong>{rowCount}</strong></p>
          {series.length ? (
            <div className="preview">
              <h3>Preview</h3>
              <pre>{JSON.stringify(series.slice(0, 8), null, 2)}</pre>
            </div>
          ) : null}
        </div>

        <div className="card">
          <h2>Forecast</h2>
          <label>
            Horizon
            <input type="number" value={horizon} min={1} max={256} onChange={e => setHorizon(e.target.value)} />
          </label>
          <button className="primary" onClick={runForecast} disabled={loading}>{loading ? 'Running forecast...' : 'Run Forecast'}</button>
          <div className="download-row">
            <button onClick={() => downloadObjectAsJson({ series }, 'series')} disabled={!series.length}>Series JSON</button>
            <button onClick={() => lastForecast && downloadObjectAsJson(lastForecast, 'forecast')} disabled={!lastForecast}>Forecast JSON</button>
            <button onClick={() => lastForecast && downloadForecastCSV(lastForecast.point, lastForecast.quantiles)} disabled={!lastForecast}>Forecast CSV</button>
          </div>
        </div>
      </section>

      <section className="chart-card">
        <h2>Forecast plot</h2>
        <div ref={plotRef} style={{ width: '100%', height: 520 }} />
      </section>
    </div>
  )
}
