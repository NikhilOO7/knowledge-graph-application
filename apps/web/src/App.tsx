import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Explorer from './pages/Explorer';
import Upload from './pages/Upload';
import Ask from './pages/Ask';
import BucketSelector from './components/BucketSelector';

const navItem =
  'group flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200';
const navActive = 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30';
const navIdle = 'text-gray-600 hover:text-gray-900 hover:bg-gray-100/80';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50/30 to-indigo-50/30">
        <nav className="bg-white/80 backdrop-blur-xl border-b border-gray-200/50 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 6a3 3 0 100-6 3 3 0 000 6zM5 21a3 3 0 100-6 3 3 0 000 6zm14 0a3 3 0 100-6 3 3 0 000 6zM12 6v6m0 0l-5 6m5-6l5 6" />
                  </svg>
                </div>
                <div className="hidden sm:block">
                  <h1 className="text-lg font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
                    Knowledge Graph
                  </h1>
                  <p className="text-xs text-gray-500 -mt-0.5">Context-bucket system</p>
                </div>
              </div>

              {/* Bucket selector — choose which context bucket's graph to view */}
              <div className="hidden md:block">
                <BucketSelector />
              </div>

              <div className="flex items-center space-x-2">
                <NavLink to="/" end className={({ isActive }) => `${navItem} ${isActive ? navActive : navIdle}`}>
                  <span className="hidden sm:inline">Dashboard</span>
                  <span className="sm:hidden">Home</span>
                </NavLink>
                <NavLink to="/explorer" className={({ isActive }) => `${navItem} ${isActive ? navActive : navIdle}`}>
                  Explorer
                </NavLink>
                <NavLink to="/ask" className={({ isActive }) => `${navItem} ${isActive ? navActive : navIdle}`}>
                  Ask
                </NavLink>
                <NavLink to="/upload" className={({ isActive }) => `${navItem} ${isActive ? navActive : navIdle}`}>
                  Upload
                </NavLink>
              </div>
            </div>
            {/* Bucket selector on small screens */}
            <div className="md:hidden pb-3">
              <BucketSelector />
            </div>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/ask" element={<Ask />} />
            <Route path="/upload" element={<Upload />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
