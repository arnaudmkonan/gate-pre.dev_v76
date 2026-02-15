import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  HardDrive, Database, Zap, FileText, Route as RouteIcon, CheckCircle,
  BarChart3, Users, Lock, AlertCircle, Eye, Repeat, LineChart, Sparkles,
  ClipboardCheck, FileCode, TrendingUp, FolderArchive, Gauge, Package,
  Shield, ArrowRightLeft, FileUp, Activity, Calculator, ChevronDown,
  ChevronRight, Building2, Settings, Upload, LogOut
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

interface AdminLayoutProps {
  children: React.ReactNode
}

interface NavItem {
  path: string
  label: string
  icon: React.ElementType
}

interface NavGroup {
  label: string
  items: NavItem[]
  collapsible?: boolean
}

export const AdminLayout = ({ children }: AdminLayoutProps) => {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set(['System']))
  const [showUserMenu, setShowUserMenu] = useState(false)

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const navGroups: NavGroup[] = [
    {
      label: 'Core',
      items: [
        { path: '/admin/dashboard', label: 'Dashboard', icon: BarChart3 },
        { path: '/entries', label: 'Customs Entries', icon: FileText },
        { path: '/clients', label: 'Clients', icon: Building2 },
      ]
    },
    {
      label: 'Documents',
      items: [
        { path: '/ingest-ui', label: 'Ingest Documents', icon: Upload },
        { path: '/shipments/assembly', label: 'Shipment Assembly', icon: Package },
        { path: '/review', label: 'Review Queue', icon: ClipboardCheck },
        { path: '/templates', label: 'Templates', icon: FileCode },
        { path: '/batch-upload', label: 'Batch Upload', icon: FolderArchive },
      ]
    },
    {
      label: 'Compliance',
      items: [
        { path: '/compliance-dashboard', label: 'Compliance Dashboard', icon: Activity },
        { path: '/trade-compliance', label: 'Trade Compliance', icon: Shield },
        { path: '/data-fabric', label: 'Data Fabric', icon: Package },
      ]
    },
    {
      label: 'Tools',
      items: [
        { path: '/tools/duty-calculator', label: 'Duty Calculator', icon: Calculator },
        { path: '/ace-import', label: 'ACE Import', icon: FileUp },
        { path: '/drawback', label: 'Duty Drawback', icon: ArrowRightLeft },
      ]
    },
    {
      label: 'AI & Analytics',
      items: [
        { path: '/agents', label: 'AI Agents', icon: Sparkles },
        { path: '/feedback', label: 'Feedback Analytics', icon: TrendingUp },
        { path: '/calibration', label: 'Calibration', icon: Gauge },
      ]
    },
    {
      label: 'Admin',
      items: [
        { path: '/admin/organizations', label: 'Organizations', icon: Users },
        { path: '/admin/roles', label: 'Roles & Permissions', icon: Lock },
        { path: '/settings/ace', label: 'ACE Settings', icon: Settings },
        { path: '/settings/platform', label: 'Platform Settings', icon: Settings },
      ]
    },
    {
      label: 'System',
      collapsible: true,
      items: [
        { path: '/admin/monitoring', label: 'Monitoring', icon: Eye },
        { path: '/admin/metrics', label: 'Metrics', icon: LineChart },
        { path: '/admin/alerts', label: 'Alerts', icon: AlertCircle },
        { path: '/admin/dlq-management', label: 'DLQ Management', icon: Database },
        { path: '/admin/retry-policy', label: 'Retry Policy', icon: Repeat },
        { path: '/admin/routing-dashboard', label: 'Routing Dashboard', icon: RouteIcon },
        { path: '/admin/extraction-status', label: 'Extraction Status', icon: CheckCircle },
        { path: '/admin/storage-config', label: 'Storage Config', icon: HardDrive },
        { path: '/admin/queue-config', label: 'Queue Config', icon: Database },
        { path: '/admin/vector-store-config', label: 'Vector Store', icon: Zap },
      ]
    },
  ]

  const isActive = (path: string) => location.pathname === path

  const toggleGroup = (label: string) => {
    setCollapsedGroups(prev => {
      const newSet = new Set(prev)
      if (newSet.has(label)) {
        newSet.delete(label)
      } else {
        newSet.add(label)
      }
      return newSet
    })
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-200 bg-white overflow-y-auto">
        <div className="p-6">
          <h1 className="text-xl font-bold text-gray-900">GATE Platform</h1>
          <p className="text-sm text-gray-500 mt-1">Customs Brokerage</p>
        </div>

        <nav className="px-4 pb-6 space-y-4">
          {navGroups.map((group) => {
            const isCollapsed = group.collapsible && collapsedGroups.has(group.label)

            return (
              <div key={group.label}>
                {group.collapsible ? (
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="flex items-center justify-between w-full px-2 py-1 text-xs font-semibold text-gray-400 uppercase tracking-wider hover:text-gray-600"
                  >
                    {group.label}
                    {isCollapsed ? (
                      <ChevronRight className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </button>
                ) : (
                  <div className="px-2 py-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {group.label}
                  </div>
                )}

                {!isCollapsed && (
                  <div className="mt-1 space-y-1">
                    {group.items.map((item) => {
                      const Icon = item.icon
                      const active = isActive(item.path)
                      return (
                        <Link
                          key={item.path}
                          to={item.path}
                          className={`
                            flex items-center px-3 py-2 rounded-lg font-medium text-sm
                            transition-colors
                            ${active
                              ? 'bg-blue-50 text-blue-700'
                              : 'text-gray-600 hover:bg-gray-50'
                            }
                          `}
                        >
                          <Icon className="w-4 h-4 mr-3" />
                          {item.label}
                        </Link>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        {/* User section */}
        {user && (
          <div className="px-4 py-4 border-t border-gray-200 mt-auto">
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="w-full flex items-center px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {user.first_name?.[0]}{user.last_name?.[0]}
                </div>
                <div className="ml-3 flex-1 text-left">
                  <p className="text-sm font-medium text-gray-700 truncate">
                    {user.first_name} {user.last_name}
                  </p>
                  <p className="text-xs text-gray-500 truncate">{user.email}</p>
                </div>
                <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
              </button>

              {showUserMenu && (
                <div className="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1">
                  <div className="px-4 py-2 border-b border-gray-100">
                    <p className="text-xs text-gray-500">Signed in as</p>
                    <p className="text-sm font-medium text-gray-700 truncate">{user.email}</p>
                    <span className="inline-block mt-1 px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full capitalize">
                      {user.role}
                    </span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
