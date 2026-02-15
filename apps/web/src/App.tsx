import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AdminLayout } from './components/AdminLayout'
import { LoginPage } from './pages/LoginPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { RegisterPage } from './pages/RegisterPage'
import { StorageConfig } from './pages/StorageConfig'
import { QueueConfig } from './pages/QueueConfig'
import { QueueMetrics } from './pages/QueueMetrics'
import { VectorStoreConfig } from './pages/VectorStoreConfig'
import { UploadPage } from './pages/UploadPage'
import { QueuePage } from './pages/QueuePage'
import { AuditPage } from './pages/AuditPage'
import { IngestQueuePage } from './pages/IngestQueuePage'
import { DLQPage } from './pages/DLQPage'
import { BatchSchedulePage } from './pages/BatchSchedulePage'
import { MetadataPage } from './pages/MetadataPage'
import { RoutingDashboardPage } from './pages/RoutingDashboardPage'
import { ExtractionStatusPage } from './pages/ExtractionStatusPage'
import { IngestUIPage } from './pages/IngestUIPage'
import { AgentPage } from './pages/AgentPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { ReviewItemDetailPage } from './pages/ReviewItemDetailPage'
import { TemplatesPage } from './pages/TemplatesPage'
import { TemplateEditorPage } from './pages/TemplateEditorPage'
import { FeedbackPage } from './pages/FeedbackPage'
import { BatchUploadPage } from './pages/BatchUploadPage'
import { CalibrationDashboardPage } from './pages/CalibrationDashboardPage'
import { DataFabricPage } from './pages/DataFabricPage'
import { TradeCompliancePage } from './pages/TradeCompliancePage'
import { DrawbackPage } from './pages/DrawbackPage'
import { ACEImportPage } from './pages/ACEImportPage'
import { ComplianceDashboardPage } from './pages/ComplianceDashboardPage'
import AdminDashboard from './pages/AdminDashboard'
import AdminOrganizations from './pages/AdminOrganizations'
import AdminRoles from './pages/AdminRoles'
import MonitoringPage from './pages/MonitoringPage'
import AlertsPage from './pages/AlertsPage'
import DLQManagementPage from './pages/DLQManagementPage'
import RetryPolicyPage from './pages/RetryPolicyPage'
import MetricsPage from './pages/MetricsPage'
import { EntriesListPage } from './pages/EntriesListPage'
import { EntryDetailPage } from './pages/EntryDetailPage'
import { NewEntryPage } from './pages/NewEntryPage'
import { DutyCalculatorPage } from './pages/DutyCalculatorPage'
import { ClientsListPage } from './pages/ClientsListPage'
import { ClientDetailPage } from './pages/ClientDetailPage'
import { NewClientPage } from './pages/NewClientPage'
import { ACESettingsPage } from './pages/ACESettingsPage'
import { LeadManagementPage } from './pages/LeadManagementPage'
import EmbeddingsManagementPage from './pages/EmbeddingsManagementPage'
import { ShipmentSuggestionsPage } from './pages/ShipmentSuggestionsPage'
import { ShipmentDetailPage } from './pages/ShipmentDetailPage'
import { EntryPrepPage } from './pages/EntryPrepPage'
import { SettingsPage } from './pages/SettingsPage'


function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes */}
          <Route
            path="/upload/:fileId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <UploadPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <UploadPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/queue"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <QueuePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/audit"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AuditPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/storage-config"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <StorageConfig />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/queue-config"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <QueueConfig />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/queue-metrics"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <QueueMetrics />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/vector-store-config"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <VectorStoreConfig />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/ingest"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <IngestQueuePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/dlq"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <DLQPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/batch-schedules"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <BatchSchedulePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/metadata"
            element={
              <ProtectedRoute>
                <MetadataPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/routing-dashboard"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <RoutingDashboardPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/extraction-status"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ExtractionStatusPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/ingest-ui"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <IngestUIPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/dashboard"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AdminDashboard />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/organizations"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <AdminOrganizations />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/roles"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <AdminRoles />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/monitoring"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <MonitoringPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/alerts"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AlertsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/dlq-management"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <DLQManagementPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/retry-policy"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <RetryPolicyPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/metrics"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <MetricsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/agents"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AgentPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/review"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ReviewQueuePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/review/:itemId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ReviewItemDetailPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/templates"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <TemplatesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/templates/:templateId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <TemplateEditorPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/feedback"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <FeedbackPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/batch-upload"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <BatchUploadPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/calibration"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <CalibrationDashboardPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/data-fabric"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <DataFabricPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/trade-compliance"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <TradeCompliancePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/drawback"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <DrawbackPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/ace-import"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ACEImportPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/compliance-dashboard"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ComplianceDashboardPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/entries"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <EntriesListPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/entries/new"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <NewEntryPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/entries/:entryId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <EntryDetailPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/entries/:entryId/edit"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <EntryDetailPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/shipments/assembly"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ShipmentSuggestionsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/shipments/:shipmentId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ShipmentDetailPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/entries/prep/:shipmentId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <EntryPrepPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/tools/duty-calculator"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <DutyCalculatorPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/clients"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ClientsListPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/clients/new"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <NewClientPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/clients/:clientId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ClientDetailPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/clients/:clientId/edit"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ClientDetailPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/ace"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <ACESettingsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/platform"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <SettingsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/leads"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <LeadManagementPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/embeddings"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminLayout>
                  <EmbeddingsManagementPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/ingest-ui" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  )
}

export default App
