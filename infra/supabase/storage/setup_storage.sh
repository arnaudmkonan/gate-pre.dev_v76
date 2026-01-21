#!/bin/bash
# Setup Supabase Storage bucket with proper policies
# Requires: supabase-cli installed

set -e

PROJECT_NAME="${1:-doc-ingestion}"
BUCKET_NAME="${2:-raw-files}"

echo "🔧 Setting up Supabase Storage bucket: $BUCKET_NAME"

# Note: Bucket creation is typically done via Supabase Dashboard or API
# This script documents the configuration steps

cat << EOF

To create the storage bucket in your Supabase project:

1. Go to https://supabase.com/dashboard
2. Select your project
3. Navigate to Storage
4. Click "New bucket"
5. Name: $BUCKET_NAME
6. Privacy: Private (recommended)
7. Click "Create bucket"

Enable S3 Access:

1. Go to Settings → API
2. Under "Project API keys", note your:
   - URL (endpoint)
   - Service Role Key (for admin access)
   - Anon Key (for public access)

3. Go to Settings → S3
4. Toggle "Enable S3 access"
5. Note the S3 endpoint: https://<project-id>.supabase.co/storage/v1/s3

Configure RLS Policies (if using authenticated uploads):

1. Go to Storage → Policies
2. Add a new policy:
   - Authenticated users can upload to their own folders
   - Authenticated users can read their own files

Example policy:
  - Target roles: authenticated
  - Query: INSERT
  - With check: (storage.foldername(name)[1] = auth.uid()::text)

EOF

echo ""
echo "✓ Follow the steps above to complete setup"
echo ""
echo "Environment variables to set:"
echo "  SUPABASE_STORAGE_ENDPOINT=https://<project>.supabase.co/storage/v1/s3"
echo "  SUPABASE_STORAGE_ACCESS_KEY=<your-s3-access-key>"
echo "  SUPABASE_STORAGE_SECRET_KEY=<your-s3-secret-key>"
echo "  SUPABASE_STORAGE_BUCKET=$BUCKET_NAME"
