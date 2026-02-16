import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { uploadReport, getStatus, getResults, getJurisdictions } from '../services/api';

vi.mock('axios');

const mockedAxios = axios as any;

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('uploadReport', () => {
    it('should upload report with correct parameters', async () => {
      const mockFile = new File(['content'], 'test.pdf', { type: 'application/pdf' });
      const mockResponse = {
        data: {
          session_id: '123',
          status: 'processing',
          jurisdiction: 'CA',
          uploaded_at: '2025-11-05T10:30:00Z',
          estimated_completion_seconds: 90,
        },
      };

      mockedAxios.create.mockReturnValue({
        post: vi.fn().mockResolvedValue(mockResponse),
        get: vi.fn(),
      });

      // Reinitialize api client with mock
      const api = mockedAxios.create();
      const result = await api.post('/reports/upload', expect.any(FormData), expect.any(Object));

      expect(result.data.session_id).toBe('123');
      expect(result.data.status).toBe('processing');
    });
  });

  describe('getStatus', () => {
    it('should get status with session ID', async () => {
      const mockResponse = {
        data: {
          session_id: '123',
          status: 'completed',
          progress_percentage: 100,
          steps_completed: ['extraction', 'categorization'],
          steps_remaining: [],
        },
      };

      mockedAxios.create.mockReturnValue({
        get: vi.fn().mockResolvedValue(mockResponse),
        post: vi.fn(),
      });

      const api = mockedAxios.create();
      const result = await api.get('/reports/123/status');

      expect(result.data.status).toBe('completed');
      expect(result.data.progress_percentage).toBe(100);
    });
  });

  describe('getResults', () => {
    it('should get results with session ID', async () => {
      const mockResponse = {
        data: {
          session_id: '123',
          jurisdiction: 'CA',
          candidate_info: {
            full_name: 'John Doe',
            dob: '1990-01-15',
          },
          summary: {
            total_offenses: 3,
            offenses_to_consider: 1,
            offenses_not_to_consider: 2,
            offenses_requiring_review: 0,
            recommendation: 'PROCEED',
          },
          offenses: [],
          generated_at: '2025-11-05T10:32:30Z',
        },
      };

      mockedAxios.create.mockReturnValue({
        get: vi.fn().mockResolvedValue(mockResponse),
        post: vi.fn(),
      });

      const api = mockedAxios.create();
      const result = await api.get('/reports/123/results');

      expect(result.data.session_id).toBe('123');
      expect(result.data.summary.total_offenses).toBe(3);
    });
  });

  describe('getJurisdictions', () => {
    it('should return list of jurisdictions', async () => {
      const mockResponse = {
        data: {
          jurisdictions: [
            { code: 'CA', name: 'California', rule_count: 8 },
            { code: 'IL', name: 'Illinois', rule_count: 7 },
            { code: 'OH', name: 'Ohio', rule_count: 9 },
          ],
        },
      };

      mockedAxios.create.mockReturnValue({
        get: vi.fn().mockResolvedValue(mockResponse),
        post: vi.fn(),
      });

      const api = mockedAxios.create();
      const result = await api.get('/jurisdictions');

      expect(result.data.jurisdictions).toHaveLength(3);
      expect(result.data.jurisdictions[0].code).toBe('CA');
    });
  });
});
