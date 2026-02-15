import React, { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Chip,
    CircularProgress,
    Alert,
    AlertTitle,
    LinearProgress,
    Grid,
    Tooltip,
    Checkbox,
    Snackbar,
} from '@mui/material';
import {
    Refresh as RefreshIcon,
    CloudUpload as GenerateIcon,
    Memory as EmbeddingIcon,
    CheckCircle as SuccessIcon,
} from '@mui/icons-material';

import { API_BASE } from '../config/api';

interface EmbeddingStats {
    total_documents: number;
    documents_with_embeddings: number;
    documents_missing_embeddings: number;
    total_embedding_chunks: number;
    coverage_percentage: number;
}

interface DocumentMissingEmbedding {
    id: string;
    filename: string;
    file_type: string;
    size: number;
    ingestion_status: string;
    extracted_text_length: number;
    created_at: string;
}

interface MissingEmbeddingsResponse {
    documents: DocumentMissingEmbedding[];
    total_count: number;
    can_generate: boolean;
    api_key_configured: boolean;
}

const EmbeddingsManagementPage: React.FC = () => {
    const [stats, setStats] = useState<EmbeddingStats | null>(null);
    const [missingDocs, setMissingDocs] = useState<MissingEmbeddingsResponse | null>(null);
    const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({
        open: false,
        message: '',
        severity: 'info',
    });

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [statsRes, missingRes] = await Promise.all([
                fetch(`${API_BASE}/api/embeddings/stats`),
                fetch(`${API_BASE}/api/embeddings/missing?limit=100`),
            ]);

            if (!statsRes.ok || !missingRes.ok) {
                throw new Error('Failed to fetch embedding data');
            }

            const statsData = await statsRes.json();
            const missingData = await missingRes.json();

            setStats(statsData);
            setMissingDocs(missingData);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleSelectAll = () => {
        if (selectedDocs.size === missingDocs?.documents.length) {
            setSelectedDocs(new Set());
        } else {
            setSelectedDocs(new Set(missingDocs?.documents.map((d) => d.id) || []));
        }
    };

    const handleSelectDoc = (docId: string) => {
        const newSelected = new Set(selectedDocs);
        if (newSelected.has(docId)) {
            newSelected.delete(docId);
        } else {
            newSelected.add(docId);
        }
        setSelectedDocs(newSelected);
    };

    const handleGenerateEmbeddings = async (generateAll: boolean = false) => {
        setGenerating(true);
        try {
            const body: { document_ids?: string[]; batch_size: number } = {
                batch_size: 50,
            };

            if (!generateAll && selectedDocs.size > 0) {
                body.document_ids = Array.from(selectedDocs);
            }

            const response = await fetch(`${API_BASE}/api/embeddings/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(body),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to generate embeddings');
            }

            const result = await response.json();

            setSnackbar({
                open: true,
                message: result.message || `Queued embedding generation for ${result.documents_queued} documents`,
                severity: 'success',
            });

            // Refresh data after a short delay
            setTimeout(() => {
                fetchData();
                setSelectedDocs(new Set());
            }, 2000);

        } catch (err) {
            setSnackbar({
                open: true,
                message: err instanceof Error ? err.message : 'Failed to generate embeddings',
                severity: 'error',
            });
        } finally {
            setGenerating(false);
        }
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const formatDate = (dateStr: string): string => {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleString();
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
                <CircularProgress size={60} />
            </Box>
        );
    }

    return (
        <Box sx={{ p: 3 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <EmbeddingIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                    <Box>
                        <Typography variant="h4" fontWeight="bold">
                            Embeddings Management
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Generate and manage vector embeddings for semantic search
                        </Typography>
                    </Box>
                </Box>
                <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={fetchData}
                    disabled={loading}
                >
                    Refresh
                </Button>
            </Box>

            {/* Error Alert */}
            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    <AlertTitle>Error</AlertTitle>
                    {error}
                </Alert>
            )}

            {/* API Key Warning */}
            {missingDocs && !missingDocs.api_key_configured && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                    <AlertTitle>OpenAI API Key Not Configured</AlertTitle>
                    Embedding generation requires an OpenAI API key. Please configure OPENAI_API_KEY in your environment.
                </Alert>
            )}

            {/* Statistics Cards */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: 'primary.main', color: 'white' }}>
                        <CardContent>
                            <Typography variant="overline">Total Documents</Typography>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.total_documents || 0}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: 'success.main', color: 'white' }}>
                        <CardContent>
                            <Typography variant="overline">With Embeddings</Typography>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.documents_with_embeddings || 0}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: stats?.documents_missing_embeddings ? 'warning.main' : 'grey.400', color: 'white' }}>
                        <CardContent>
                            <Typography variant="overline">Missing Embeddings</Typography>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.documents_missing_embeddings || 0}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: 'info.main', color: 'white' }}>
                        <CardContent>
                            <Typography variant="overline">Total Chunks</Typography>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.total_embedding_chunks || 0}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Coverage Progress */}
            <Card sx={{ mb: 4 }}>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6">Embedding Coverage</Typography>
                        <Chip
                            label={`${stats?.coverage_percentage || 0}%`}
                            color={
                                (stats?.coverage_percentage || 0) >= 80 ? 'success' :
                                    (stats?.coverage_percentage || 0) >= 50 ? 'warning' : 'error'
                            }
                        />
                    </Box>
                    <LinearProgress
                        variant="determinate"
                        value={stats?.coverage_percentage || 0}
                        sx={{ height: 10, borderRadius: 5 }}
                    />
                </CardContent>
            </Card>

            {/* Documents Missing Embeddings */}
            <Card>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6">
                            Documents Missing Embeddings ({missingDocs?.total_count || 0})
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 2 }}>
                            {selectedDocs.size > 0 && (
                                <Button
                                    variant="contained"
                                    color="primary"
                                    startIcon={generating ? <CircularProgress size={20} color="inherit" /> : <GenerateIcon />}
                                    onClick={() => handleGenerateEmbeddings(false)}
                                    disabled={generating || !missingDocs?.api_key_configured}
                                >
                                    Generate for Selected ({selectedDocs.size})
                                </Button>
                            )}
                            <Button
                                variant="outlined"
                                color="primary"
                                startIcon={generating ? <CircularProgress size={20} color="inherit" /> : <GenerateIcon />}
                                onClick={() => handleGenerateEmbeddings(true)}
                                disabled={generating || !missingDocs?.can_generate}
                            >
                                Generate All Missing
                            </Button>
                        </Box>
                    </Box>

                    {missingDocs?.documents.length === 0 ? (
                        <Alert severity="success" icon={<SuccessIcon />}>
                            All documents have embeddings! No action needed.
                        </Alert>
                    ) : (
                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow sx={{ bgcolor: 'grey.100' }}>
                                        <TableCell padding="checkbox">
                                            <Checkbox
                                                indeterminate={selectedDocs.size > 0 && selectedDocs.size < (missingDocs?.documents.length || 0)}
                                                checked={selectedDocs.size === (missingDocs?.documents.length || 0) && selectedDocs.size > 0}
                                                onChange={handleSelectAll}
                                            />
                                        </TableCell>
                                        <TableCell><strong>Filename</strong></TableCell>
                                        <TableCell><strong>Type</strong></TableCell>
                                        <TableCell><strong>Size</strong></TableCell>
                                        <TableCell><strong>Text Length</strong></TableCell>
                                        <TableCell><strong>Status</strong></TableCell>
                                        <TableCell><strong>Created</strong></TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {missingDocs?.documents.map((doc) => (
                                        <TableRow
                                            key={doc.id}
                                            hover
                                            selected={selectedDocs.has(doc.id)}
                                            onClick={() => handleSelectDoc(doc.id)}
                                            sx={{ cursor: 'pointer' }}
                                        >
                                            <TableCell padding="checkbox">
                                                <Checkbox checked={selectedDocs.has(doc.id)} />
                                            </TableCell>
                                            <TableCell>
                                                <Tooltip title={doc.id}>
                                                    <Typography variant="body2" noWrap sx={{ maxWidth: 300 }}>
                                                        {doc.filename}
                                                    </Typography>
                                                </Tooltip>
                                            </TableCell>
                                            <TableCell>
                                                <Chip label={doc.file_type} size="small" variant="outlined" />
                                            </TableCell>
                                            <TableCell>{formatFileSize(doc.size)}</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={`${doc.extracted_text_length} chars`}
                                                    size="small"
                                                    color={doc.extracted_text_length > 100 ? 'success' : 'warning'}
                                                    variant="outlined"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={doc.ingestion_status}
                                                    size="small"
                                                    color={doc.ingestion_status === 'completed' ? 'success' : 'default'}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2" color="text.secondary">
                                                    {formatDate(doc.created_at)}
                                                </Typography>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </CardContent>
            </Card>

            {/* Snackbar for notifications */}
            <Snackbar
                open={snackbar.open}
                autoHideDuration={6000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            >
                <Alert
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                    severity={snackbar.severity}
                    sx={{ width: '100%' }}
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default EmbeddingsManagementPage;
