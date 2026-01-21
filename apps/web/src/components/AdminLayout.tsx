import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { HardDrive, Database, Zap, FileText, Route as RouteIcon, CheckCircle, BarChart3, Users, Lock, AlertCircle, Eye, Repeat, LineChart } from 'lucide-react'

interface AdminLayoutProps {
  children: React.ReactNode
}

export const AdminLayout = ({ children }: AdminLayoutProps) => {
  const location = useLocation()

  const navItems = [
    { path: '/admin/dashboard', label: 'Dashboard', icon: BarChart3 },
    { path: '/admin/organizations', label: 'Organizations', icon: Users },
    { path: '/admin/roles', label: 'Roles & Permissions', icon: Lock },
    { path: '/metadata', label: 'Metadata Search', icon: FileText },
    { path: '/admin/routing-dashboard', label: 'Routing Dashboard', icon: RouteIcon },
    { path: '/admin/extraction-status', label: 'Extraction Status', icon: CheckCircle },
    { path: '/admin/storage-config', label: 'Storage', icon: HardDrive },
    { path: '/admin/queue-config', label: 'Queue', icon: Database },
    { path: '/admin/vector-store-config', label: 'Vector Store', icon: Zap },
    { path: '/admin/monitoring', label: 'Monitoring', icon: Eye },
    { path: '/admin/metrics', label: 'Metrics', icon: LineChart },
    { path: '/admin/alerts', label: 'Alerts', icon: AlertCircle },
    { path: '/admin/dlq-management', label: 'DLQ Management', icon: Database },
    { path: '/admin/retry-policy', label: 'Retry Policy', icon: Repeat },
  ]

  const isActive = (path: string) => location.pathname === path

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-200 bg-white">
        <div className="p-6">
          <h1 className="text-xl font-bold text-gray-900">Admin Panel</h1>
          <p className="text-sm text-gray-500 mt-1">Doc Ingestion Platform</p>
        </div>

        <nav className="space-y-1 px-4 py-6">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`
                  flex items-center px-4 py-3 rounded-lg font-medium text-sm
                  transition-colors
                  ${
                    active
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  }
                `}
              >
                <Icon className="w-5 h-5 mr-3" />
                {item.label}
              </Link>
            )
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
