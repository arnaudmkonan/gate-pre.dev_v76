import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AdminLayout } from './components/AdminLayout'
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
import AdminDashboard from './pages/AdminDashboard'
import AdminOrganizations from './pages/AdminOrganizations'
import AdminRoles from './pages/AdminRoles'
import MonitoringPage from './pages/MonitoringPage'
import AlertsPage from './pages/AlertsPage'
import DLQManagementPage from './pages/DLQManagementPage'
import RetryPolicyPage from './pages/RetryPolicyPage'
import MetricsPage from './pages/MetricsPage'


function App() {
  return (
    <Router>
      <Routes>
        <Route
          path="/upload/:fileId"
          element={
            <AdminLayout>
              <UploadPage />
            </AdminLayout>
          }
        />
        <Route
          path="/upload"
          element={
            <AdminLayout>
              <UploadPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/queue"
          element={
            <AdminLayout>
              <QueuePage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/audit"
          element={
            <AdminLayout>
              <AuditPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/storage-config"
          element={
            <AdminLayout>
              <StorageConfig />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/queue-config"
          element={
            <AdminLayout>
              <QueueConfig />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/queue-metrics"
          element={
            <AdminLayout>
              <QueueMetrics />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/vector-store-config"
          element={
            <AdminLayout>
              <VectorStoreConfig />
            </AdminLayout>
          }
        />
        <Route
          path="/ingest"
          element={
            <AdminLayout>
              <IngestQueuePage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/dlq"
          element={
            <AdminLayout>
              <DLQPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/batch-schedules"
          element={
            <AdminLayout>
              <BatchSchedulePage />
            </AdminLayout>
          }
        />
        <Route
          path="/metadata"
          element={<MetadataPage />}
        />
        <Route
          path="/admin/routing-dashboard"
          element={
            <AdminLayout>
              <RoutingDashboardPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/extraction-status"
          element={
            <AdminLayout>
              <ExtractionStatusPage />
            </AdminLayout>
          }
        />
        <Route
          path="/ingest-ui"
          element={
            <AdminLayout>
              <IngestUIPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/dashboard"
          element={
            <AdminLayout>
              <AdminDashboard />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/organizations"
          element={
            <AdminLayout>
              <AdminOrganizations />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/roles"
          element={
            <AdminLayout>
              <AdminRoles />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/monitoring"
          element={
            <AdminLayout>
              <MonitoringPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/alerts"
          element={
            <AdminLayout>
              <AlertsPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/dlq-management"
          element={
            <AdminLayout>
              <DLQManagementPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/retry-policy"
          element={
            <AdminLayout>
              <RetryPolicyPage />
            </AdminLayout>
          }
        />
        <Route
          path="/admin/metrics"
          element={
            <AdminLayout>
              <MetricsPage />
            </AdminLayout>
          }
        />
        <Route
          path="/agents"
          element={
            <AdminLayout>
              <AgentPage />
            </AdminLayout>
          }
        />
        <Route
          path="/review"
          element={
            <AdminLayout>
              <ReviewQueuePage />
            </AdminLayout>
          }
        />
        <Route
          path="/review/:itemId"
          element={
            <AdminLayout>
              <ReviewItemDetailPage />
            </AdminLayout>
          }
        />
        <Route
          path="/templates"
          element={
            <AdminLayout>
              <TemplatesPage />
            </AdminLayout>
          }
        />
        <Route
          path="/templates/:templateId"
          element={
            <AdminLayout>
              <TemplateEditorPage />
            </AdminLayout>
          }
        />
        <Route
          path="/feedback"
          element={
            <AdminLayout>
              <FeedbackPage />
            </AdminLayout>
          }
        />
        <Route
          path="/batch-upload"
          element={
            <AdminLayout>
              <BatchUploadPage />
            </AdminLayout>
          }
        />
        <Route
          path="/calibration"
          element={
            <AdminLayout>
              <CalibrationDashboardPage />
            </AdminLayout>
          }
        />
        <Route
          path="/data-fabric"
          element={
            <AdminLayout>
              <DataFabricPage />
            </AdminLayout>
          }
        />
        <Route
          path="/trade-compliance"
          element={
            <AdminLayout>
              <TradeCompliancePage />
            </AdminLayout>
          }
        />
        <Route
          path="/drawback"
          element={
            <AdminLayout>
              <DrawbackPage />
            </AdminLayout>
          }
        />
        <Route
          path="/ace-import"
          element={
            <AdminLayout>
              <ACEImportPage />
            </AdminLayout>
          }
        />
        <Route path="/" element={<Navigate to="/ingest-ui" replace />} />
      </Routes>
    </Router>
  )
}

export default App
