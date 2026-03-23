import SearchPage from './pages/SearchPage'
import './App.css'

function App() {
  return (
    <>
      <div className="accent-stripe" />
      <nav className="nav">
        <div className="nav-inner">
          <a href="/" className="nav-brand">
            <span className="nav-brand-icon">⚡</span>
            Patent Connector
          </a>
        </div>
      </nav>
      <main className="main">
        <SearchPage />
      </main>
      <footer className="footer">
        <div className="footer-inner">
          <span className="footer-brand">blinktask.work</span>
          <span className="footer-version">v0.1.0</span>
        </div>
      </footer>
    </>
  )
}

export default App
