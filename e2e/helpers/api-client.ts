import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { APIRequestContext } from '@playwright/test';

const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), '../..');

export type AuthSession = {
  token: string;
  user: { email: string; role: string; id?: string };
};

export class GateApiClient {
  constructor(
    private readonly request: APIRequestContext,
    private readonly baseURL: string,
  ) {}

  async login(email: string, password: string): Promise<AuthSession> {
    const res = await this.request.post(`${this.baseURL}/api/portal/login`, {
      data: { email, password },
    });
    if (!res.ok()) {
      throw new Error(`Login failed (${res.status()}): ${await res.text()}`);
    }
    const json = await res.json();
    return { token: json.session_token, user: json.user };
  }

  private headers(token: string, extra?: Record<string, string>) {
    return { Authorization: `Bearer ${token}`, ...extra };
  }

  async uploadDocument(
    token: string,
    filePath: string,
    source = 'playwright_e2e',
  ): Promise<{ job_id: string; file_id: string; status: string }> {
    const fileName = path.basename(filePath);
    const res = await this.request.post(`${this.baseURL}/api/upload`, {
      headers: this.headers(token),
      multipart: {
        file: {
          name: fileName,
          mimeType: mimeFor(fileName),
          buffer: fs.readFileSync(filePath),
        },
        source,
      },
    });
    if (!res.ok()) {
      throw new Error(`Upload failed for ${fileName} (${res.status()}): ${await res.text()}`);
    }
    return res.json();
  }

  async pollIngestJobs(
    token: string,
    jobIds: string[],
    options: { timeoutMs?: number; intervalMs?: number } = {},
  ): Promise<{ completed: number; failed: number; jobs: Record<string, string> }> {
    const timeoutMs = options.timeoutMs ?? 300_000;
    const intervalMs = options.intervalMs ?? 3_000;
    const deadline = Date.now() + timeoutMs;
    const statuses: Record<string, string> = {};

    while (Date.now() < deadline) {
      const res = await this.request.get(
        `${this.baseURL}/api/ingest/jobs?page=1&page_size=100`,
        { headers: this.headers(token) },
      );
      if (!res.ok()) {
        throw new Error(`List jobs failed: ${await res.text()}`);
      }
      const body = await res.json();
      const jobs: Array<{ id: string; status: string }> = body.jobs ?? [];
      for (const id of jobIds) {
        const job = jobs.find((j) => j.id === id);
        if (job) statuses[id] = job.status;
      }
      const completed = jobIds.filter((id) => statuses[id] === 'completed').length;
      const failed = jobIds.filter((id) => statuses[id] === 'failed').length;
      if (completed + failed === jobIds.length) {
        return { completed, failed, jobs: statuses };
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    throw new Error(
      `Timed out waiting for jobs. Last statuses: ${JSON.stringify(statuses)}`,
    );
  }

  async getReviewQueue(token: string) {
    const res = await this.request.get(`${this.baseURL}/api/review/queue?limit=50`, {
      headers: this.headers(token),
    });
    if (!res.ok()) throw new Error(`Review queue failed: ${await res.text()}`);
    return res.json();
  }

  async getShipments(token: string) {
    const res = await this.request.get(`${this.baseURL}/api/shipments?limit=50`, {
      headers: this.headers(token),
    });
    if (!res.ok()) throw new Error(`Shipments failed: ${await res.text()}`);
    return res.json();
  }

  async getShipmentSuggestions(token: string) {
    const res = await this.request.get(`${this.baseURL}/api/shipments/suggestions`, {
      headers: this.headers(token),
    });
    if (!res.ok()) throw new Error(`Shipment suggestions failed: ${await res.text()}`);
    return res.json();
  }

  async getEntries(token: string) {
    const res = await this.request.get(`${this.baseURL}/api/entries?limit=50`, {
      headers: this.headers(token),
    });
    if (!res.ok()) throw new Error(`Entries failed: ${await res.text()}`);
    return res.json();
  }

  async getQueueStatus(token: string) {
    const res = await this.request.get(`${this.baseURL}/api/queue/status`, {
      headers: this.headers(token),
    });
    if (!res.ok()) throw new Error(`Queue status failed: ${await res.text()}`);
    return res.json();
  }

  async createLead(payload: Record<string, string>) {
    const res = await this.request.post(`${this.baseURL}/api/leads`, { data: payload });
    if (!res.ok()) throw new Error(`Create lead failed: ${await res.text()}`);
    return res.json();
  }

  async trackLandingEvent(payload: Record<string, unknown>) {
    const res = await this.request.post(`${this.baseURL}/api/analytics/landing/track`, {
      data: payload,
    });
    if (!res.ok()) throw new Error(`Landing track failed: ${await res.text()}`);
    return res.json();
  }

  async validateNormalization(token: string, body: unknown) {
    const res = await this.request.post(
      `${this.baseURL}/api/validation/validate-normalization`,
      { headers: this.headers(token), data: body },
    );
    if (!res.ok()) throw new Error(`Validation failed: ${await res.text()}`);
    return res.json();
  }
}

function mimeFor(fileName: string): string {
  const ext = path.extname(fileName).toLowerCase();
  const map: Record<string, string> = {
    '.pdf': 'application/pdf',
    '.txt': 'text/plain',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  };
  return map[ext] ?? 'application/octet-stream';
}

export function listDemoFiles(relativeDir: string): string[] {
  const dir = path.join(repoRoot, relativeDir);
  return fs
    .readdirSync(dir)
    .filter((f) => !f.startsWith('.'))
    .map((f) => path.join(dir, f))
    .filter((p) => fs.statSync(p).isFile())
    .sort();
}
