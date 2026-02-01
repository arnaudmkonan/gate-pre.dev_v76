import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  HardDrive, Database, Zap, FileText, Route as RouteIcon, CheckCircle,
  BarChart3, Users, Lock, AlertCircle, Eye, Repeat, LineChart, Sparkles,
  ClipboardCheck, FileCode, TrendingUp, FolderArchive, Gauge, Package,
  Shield, ArrowRightLeft, FileUp, Activity, Calculator, ChevronDown,
  ChevronRight, Building2, Settings, Upload
} from 'lucide-react'

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
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set(['System']))

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
