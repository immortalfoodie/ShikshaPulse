import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import About from './pages/About'
import Actions from './pages/Actions'
import Block from './pages/Block'
import Brief from './pages/Brief'
import CommandCenter from './pages/CommandCenter'
import DataStudio from './pages/DataStudio'
import Guide from './pages/Guide'
import Lab from './pages/Lab'
import Login from './pages/Login'
import MySchool from './pages/MySchool'
import Peers from './pages/Peers'
import RadarPage from './pages/Radar'
import ReportCard from './pages/ReportCard'
import Review from './pages/Review'
import Visits from './pages/Visits'
import Why from './pages/Why'
import { useApp } from './state'

export default function App() {
  const { user, meta } = useApp()
  if (!user) return <Login />
  if (!meta) return <Spinner />
  if (user.role === 'headmaster') {
    return (
      <Layout>
        <Routes>
          <Route path="/actions" element={<Actions />} />
          <Route path="/about" element={<About />} />
          <Route path="/guide" element={<Guide />} />
          <Route path="/report-card/:udise" element={<ReportCard />} />
          <Route path="*" element={<MySchool />} />
        </Routes>
      </Layout>
    )
  }
  return (
    <Layout>
      {!meta.ready ? (
        <Routes>
          <Route path="*" element={<DataStudio />} />
        </Routes>
      ) : (
        <Routes>
          <Route path="/" element={user.crc ? <Visits /> : <CommandCenter />} />
          <Route path="/visits" element={<Visits />} />
          <Route path="/overview" element={<CommandCenter />} />
          <Route path="/review" element={<Review />} />
          <Route path="/report-card/:udise" element={<ReportCard />} />
          <Route path="/why" element={<Why />} />
          <Route path="/block" element={<Block />} />
          <Route path="/peers" element={<Peers />} />
          <Route path="/radar" element={<RadarPage />} />
          <Route path="/actions" element={<Actions />} />
          <Route path="/data" element={<DataStudio />} />
          <Route path="/brief" element={<Brief />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/about" element={<About />} />
          <Route path="/guide" element={<Guide />} />
          <Route path="*" element={<CommandCenter />} />
        </Routes>
      )}
    </Layout>
  )
}
