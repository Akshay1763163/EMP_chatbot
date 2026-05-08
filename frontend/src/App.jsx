import { useState } from 'react'
import './App.css'

const apiBase = import.meta.env.VITE_API_BASE || '/api'

const formatSalary = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
}).format

function App() {
  const [employeeId, setEmployeeId] = useState('')
  const [employeeDetail, setEmployeeDetail] = useState(null)
  const [employeeLoading, setEmployeeLoading] = useState(false)
  const [employeeError, setEmployeeError] = useState('')

  const [chatMessages, setChatMessages] = useState([
    {
      role: 'assistant',
      content:
        'Ask me about employees by name, id, or join date (YYYY-MM-DD).',
    },
  ])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState('')
  const [chatResults, setChatResults] = useState([])
  const [chatSql, setChatSql] = useState('')

  function formatActiveStatus(active) {
    return active ? 'Active' : 'Inactive'
  }

  async function handleLookup(event) {
    event.preventDefault()
    setEmployeeDetail(null)
    setEmployeeError('')

    const normalizedId = Number(employeeId)
    if (!normalizedId) {
      setEmployeeError('Enter a valid employee id.')
      return
    }

    setEmployeeLoading(true)
    try {
      const response = await fetch(`${apiBase}/employees/${normalizedId}`)
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Employee not found.')
        }
        throw new Error('Failed to fetch employee.')
      }
      const data = await response.json()
      setEmployeeDetail(data)
    } catch (error) {
      setEmployeeError(error.message || 'Unexpected error')
    } finally {
      setEmployeeLoading(false)
    }
  }

  async function handleChatSubmit(event) {
    event.preventDefault()
    const trimmed = chatInput.trim()
    if (!trimmed || chatLoading) {
      return
    }

    setChatError('')
    setChatInput('')
    setChatSql('')
    setChatLoading(true)
    setChatMessages((prev) => [...prev, { role: 'user', content: trimmed }])

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 20000)

    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: trimmed }),
        signal: controller.signal,
      })

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error('AI rate limit reached. Please try again soon.')
        }
        throw new Error('Unable to reach the assistant.')
      }

      const data = await response.json()
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.reply || 'No reply received.' },
      ])
      setChatResults(Array.isArray(data.results) ? data.results : [])
      setChatSql(data.sql || '')
    } catch (error) {
      if (error.name === 'AbortError') {
        setChatError(
          'Request timed out. The AI service may be rate-limited. Please try again.'
        )
      } else {
        setChatError(error.message || 'Unexpected error')
      }
    } finally {
      clearTimeout(timeoutId)
      setChatLoading(false)
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">EmployeeDB Live</p>
          <h1>Employee roster at a glance.</h1>
          <p className="lead">
            Connected to SQL Server with FastAPI. Lookup a single record by
            ID and ask complex questions through the assistant.
          </p>
        </div>
        <div className="hero-card">
          <div>
            <p className="label">Quick lookup</p>
            <h2>Employee ID</h2>
          </div>
        </div>
      </header>

      <section className="lookup">
        <form className="lookup-form" onSubmit={handleLookup}>
          <div>
            <label htmlFor="employee-id">Employee id</label>
            <input
              id="employee-id"
              type="number"
              min="1"
              placeholder="Enter id"
              value={employeeId}
              onChange={(event) => setEmployeeId(event.target.value)}
            />
          </div>
          <button type="submit" disabled={employeeLoading}>
            {employeeLoading ? 'Searching...' : 'Find employee'}
          </button>
        </form>

        <div className="lookup-result">
          {employeeError && <p className="error">{employeeError}</p>}
          {!employeeError && employeeDetail && (
            <div className="detail-card">
              <div>
                <p className="label">Name</p>
                <p className="value">{employeeDetail.name}</p>
              </div>
              <div>
                <p className="label">Role</p>
                <p className="value">{employeeDetail.role}</p>
              </div>
              <div>
                <p className="label">Department</p>
                <p className="value">{employeeDetail.department}</p>
              </div>
              <div>
                <p className="label">Joined</p>
                <p className="value">{employeeDetail.joined_date}</p>
              </div>
              <div>
                <p className="label">Salary</p>
                <p className="value">{formatSalary(employeeDetail.salary)}</p>
              </div>
              <div>
                <p className="label">Status</p>
                <p className="value">
                  {formatActiveStatus(employeeDetail.active)}
                </p>
              </div>
              <div>
                <p className="label">Resigned</p>
                <p className="value">
                  {employeeDetail.date_of_resign || '—'}
                </p>
              </div>
            </div>
          )}
          {!employeeError && !employeeDetail && (
            <p className="muted">Lookup results appear here.</p>
          )}
        </div>
      </section>

      <section className="chat">
        <div className="chat-header">
          <div>
            <p className="eyebrow">Assistant</p>
            <h3>Employee chat</h3>
          </div>
          <span className="badge">Groq</span>
        </div>
        <div className="chat-window">
          {chatMessages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`chat-bubble ${message.role}`}
            >
              {message.content}
            </div>
          ))}
          {chatLoading && (
            <div className="chat-bubble assistant">Thinking...</div>
          )}
        </div>
        {chatError && <p className="error">{chatError}</p>}
        <form className="chat-input" onSubmit={handleChatSubmit}>
          <input
            type="text"
            placeholder="Ask about employee details..."
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
          />
          <button type="submit" disabled={chatLoading}>
            Send
          </button>
        </form>
      </section>

      <section className="results">
        <div className="list-header">
          <h3>Query results</h3>
          <span className="badge">Latest</span>
        </div>

        {chatSql && (
          <div className="sql-block">
            <p className="label">SQL used</p>
            <pre>{chatSql}</pre>
          </div>
        )}

        {chatLoading && <p className="muted">Waiting for assistant...</p>}
        {!chatLoading && chatResults.length === 0 && (
          <p className="muted">No results yet. Ask a question above.</p>
        )}

        {chatResults.length > 0 && (
          <div className="grid">
            {chatResults.map((employee) => (
              <article key={employee.id} className="card">
                <div className="card-title">
                  <span>#{employee.id}</span>
                  <strong>{employee.name}</strong>
                </div>
                <div className="card-meta">
                  <span>{employee.role}</span>
                  <span>{employee.department}</span>
                </div>
                <div className="card-meta">
                  <span>{employee.joined_date}</span>
                  <span>{formatSalary(employee.salary)}</span>
                </div>
                <div className="card-meta">
                  <span>{formatActiveStatus(employee.active)}</span>
                  <span>{employee.date_of_resign || '—'}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export default App
