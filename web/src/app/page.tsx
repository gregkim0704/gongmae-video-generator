"use client";

import { useState, useEffect } from "react";

// API base URL - change for production
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Job {
  job_id: string;
  status: string;
  progress: number;
  current_step: string | null;
  video_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

interface Property {
  case_number: string;
  court: string;
  asset_type: string;
  asset_type_name: string;
  address: string;
  appraisal_value: number;
  minimum_bid: number;
  auction_date: string;
}

// 상태 한글 변환
const statusMap: Record<string, string> = {
  pending: "대기중",
  processing: "처리중",
  completed: "완료",
  failed: "실패",
};

export default function Home() {
  const [caseNumber, setCaseNumber] = useState("");
  const [inputMode, setInputMode] = useState("mock");
  const [mockMode, setMockMode] = useState(true);
  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);
  const [activeTab, setActiveTab] = useState<"standard" | "pdf">("standard");
  const [pdfFile, setPdfFile] = useState<File | null>(null);

  // Format Korean price
  const formatPrice = (value: number): string => {
    if (value >= 100000000) {
      const eok = Math.floor(value / 100000000);
      const remainder = value % 100000000;
      if (remainder >= 10000000) {
        const cheonman = Math.floor(remainder / 10000000);
        return `${eok}억 ${cheonman}천만원`;
      }
      return `${eok}억원`;
    }
    if (value >= 10000000) {
      return `${Math.floor(value / 10000000)}천만원`;
    }
    return `${value.toLocaleString()}원`;
  };

  // Load properties on mount and when input mode changes
  useEffect(() => {
    loadProperties();
  }, [inputMode]);

  // Poll job status when job is active
  useEffect(() => {
    if (!currentJob || currentJob.status === "completed" || currentJob.status === "failed") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/jobs/${currentJob.job_id}`);
        if (res.ok) {
          const job = await res.json();
          setCurrentJob(job);
        }
      } catch (err) {
        console.error("작업 상태 조회 실패:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentJob]);

  const loadProperties = async () => {
    try {
      const res = await fetch(`${API_URL}/api/properties?input_mode=${inputMode}`);
      if (res.ok) {
        const data = await res.json();
        setProperties(data.properties || []);
      }
    } catch (err) {
      console.error("매물 목록 조회 실패:", err);
    }
  };

  const submitJob = async () => {
    if (!caseNumber.trim()) {
      setError("사건번호를 입력해주세요");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_number: caseNumber,
          input_mode: inputMode,
          mock_mode: mockMode,
        }),
      });

      if (!res.ok) {
        throw new Error(`API 오류: ${res.status}`);
      }

      const job = await res.json();
      setCurrentJob(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "작업 제출 실패");
    } finally {
      setLoading(false);
    }
  };

  const selectProperty = (prop: Property) => {
    setCaseNumber(prop.case_number);
  };

  const handlePdfSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type === "application/pdf") {
      setPdfFile(file);
      setError(null);
    } else {
      setError("PDF 파일만 업로드 가능합니다");
    }
  };

  const submitPdfJob = async () => {
    if (!pdfFile) {
      setError("PDF 파일을 선택해주세요");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", pdfFile);

      const res = await fetch(`${API_URL}/api/upload-pdf`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `API 오류: ${res.status}`);
      }

      const job = await res.json();
      setCurrentJob(job);
      setPdfFile(null);
      // Reset file input
      const fileInput = document.getElementById("pdf-upload") as HTMLInputElement;
      if (fileInput) fileInput.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF 업로드 실패");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-800 text-white">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2">공매 영상 생성기</h1>
          <p className="text-gray-400">전문적인 경매 매물 소개 영상을 생성합니다</p>
        </header>

        {/* 사용법 가이드 */}
        <div className="bg-gray-800 rounded-xl mb-8 shadow-xl overflow-hidden">
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="w-full p-4 flex justify-between items-center hover:bg-gray-700/50 transition-colors"
          >
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <span className="text-2xl">📖</span> 사용법 안내
            </h2>
            <span className={`transform transition-transform ${showGuide ? "rotate-180" : ""}`}>
              ▼
            </span>
          </button>

          {showGuide && (
            <div className="px-6 pb-6 space-y-6">
              {/* Step 1 */}
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="text-lg font-semibold text-blue-400 mb-2">
                  1단계: 매물 선택
                </h3>
                <p className="text-gray-300 text-sm leading-relaxed">
                  아래 <span className="text-blue-400 font-medium">매물 목록</span>에서
                  영상을 생성할 매물을 클릭하세요. 클릭하면 자동으로 사건번호가 입력됩니다.
                  또는 사건번호를 직접 입력할 수도 있습니다 (예: 2024타경12345).
                </p>
              </div>

              {/* Step 2 */}
              <div className="border-l-4 border-green-500 pl-4">
                <h3 className="text-lg font-semibold text-green-400 mb-2">
                  2단계: 옵션 설정
                </h3>
                <div className="text-gray-300 text-sm leading-relaxed space-y-3">
                  <div>
                    <span className="font-medium text-white">입력 방식:</span>
                    <ul className="mt-1 ml-4 list-disc space-y-1">
                      <li><span className="text-yellow-400">테스트 데이터</span> - 미리 준비된 샘플 매물 데이터 사용</li>
                      <li><span className="text-yellow-400">JSON 파일</span> - 직접 업로드한 매물 데이터 사용</li>
                    </ul>
                  </div>
                  <div>
                    <span className="font-medium text-white">실행 모드:</span>
                    <ul className="mt-1 ml-4 list-disc space-y-1">
                      <li><span className="text-yellow-400">테스트</span> - 외부 API 호출 없이 빠르게 테스트 (무료)</li>
                      <li><span className="text-yellow-400">프로덕션</span> - 실제 TTS 음성 및 AI 스크립트 생성 (API 키 필요)</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Step 3 */}
              <div className="border-l-4 border-purple-500 pl-4">
                <h3 className="text-lg font-semibold text-purple-400 mb-2">
                  3단계: 영상 생성
                </h3>
                <p className="text-gray-300 text-sm leading-relaxed">
                  <span className="text-blue-400 font-medium">&quot;영상 생성하기&quot;</span> 버튼을 클릭하면
                  영상 생성이 시작됩니다. 진행 상황은 화면에서 실시간으로 확인할 수 있습니다.
                </p>
              </div>

              {/* Step 4 */}
              <div className="border-l-4 border-orange-500 pl-4">
                <h3 className="text-lg font-semibold text-orange-400 mb-2">
                  4단계: 영상 다운로드
                </h3>
                <p className="text-gray-300 text-sm leading-relaxed">
                  영상 생성이 완료되면 <span className="text-green-400 font-medium">&quot;영상 다운로드&quot;</span> 버튼이 나타납니다.
                  클릭하여 생성된 MP4 영상 파일을 다운로드하세요.
                </p>
              </div>

              {/* PDF Mode Guide */}
              <div className="border-l-4 border-pink-500 pl-4">
                <h3 className="text-lg font-semibold text-pink-400 mb-2">
                  PDF 감정평가서 모드
                </h3>
                <p className="text-gray-300 text-sm leading-relaxed">
                  <span className="text-purple-400 font-medium">PDF 감정평가서</span> 탭을 선택하면
                  감정평가서 PDF 파일을 업로드할 수 있습니다. AI가 자동으로 내용을 분석하여
                  나레이션 스크립트를 생성하고, 각 페이지를 슬라이드쇼 형식의 영상으로 만들어줍니다.
                </p>
              </div>

              {/* Tips */}
              <div className="bg-gray-700/50 rounded-lg p-4 mt-4">
                <h3 className="text-lg font-semibold text-yellow-400 mb-2 flex items-center gap-2">
                  <span>💡</span> 팁
                </h3>
                <ul className="text-gray-300 text-sm space-y-2">
                  <li>• 처음 사용하시면 <span className="text-yellow-400">테스트 모드</span>로 먼저 시도해보세요.</li>
                  <li>• 영상 생성에는 약 <span className="text-yellow-400">1~2분</span> 정도 소요됩니다.</li>
                  <li>• 생성된 영상은 <span className="text-yellow-400">1920x1080 (가로형)</span> 형식입니다.</li>
                  <li>• <span className="text-purple-400">PDF 모드</span>는 Claude API 키만 필요합니다 (TTS는 무료).</li>
                  <li>• 문의사항은 관리자에게 연락해주세요.</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Main Form */}
        <div className="bg-gray-800 rounded-xl p-6 mb-8 shadow-xl">
          <h2 className="text-xl font-semibold mb-4">새 영상 생성</h2>

          {/* Tab Buttons */}
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setActiveTab("standard")}
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                activeTab === "standard"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              일반 모드
            </button>
            <button
              onClick={() => setActiveTab("pdf")}
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                activeTab === "pdf"
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              PDF 감정평가서
            </button>
          </div>

          {/* Standard Mode Form */}
          {activeTab === "standard" && (
            <>
              {/* Case Number Input */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  사건번호
                </label>
                <input
                  type="text"
                  value={caseNumber}
                  onChange={(e) => setCaseNumber(e.target.value)}
                  placeholder="2024타경12345"
                  className="w-full px-4 py-3 rounded-lg bg-gray-700 border border-gray-600
                           focus:border-blue-500 focus:ring-1 focus:ring-blue-500
                           text-white placeholder-gray-400"
                />
              </div>

              {/* Options */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    입력 방식
                  </label>
                  <select
                    value={inputMode}
                    onChange={(e) => setInputMode(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg bg-gray-700 border border-gray-600 text-white"
                  >
                    <option value="mock">테스트 데이터</option>
                    <option value="json">JSON 파일</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    실행 모드
                  </label>
                  <select
                    value={mockMode ? "mock" : "production"}
                    onChange={(e) => setMockMode(e.target.value === "mock")}
                    className="w-full px-4 py-3 rounded-lg bg-gray-700 border border-gray-600 text-white"
                  >
                    <option value="mock">테스트 (API 호출 없음)</option>
                    <option value="production">프로덕션 (API 필요)</option>
                  </select>
                </div>
              </div>

              {/* Submit Button */}
              <button
                onClick={submitJob}
                disabled={loading || !!(currentJob && currentJob.status === "processing")}
                className="w-full py-3 px-6 rounded-lg bg-blue-600 hover:bg-blue-700
                         disabled:bg-gray-600 disabled:cursor-not-allowed
                         font-semibold transition-colors"
              >
                {loading ? "제출 중..." : "영상 생성하기"}
              </button>
            </>
          )}

          {/* PDF Mode Form */}
          {activeTab === "pdf" && (
            <>
              <div className="mb-6">
                <div className="bg-purple-900/30 border border-purple-700 rounded-lg p-4 mb-4">
                  <h3 className="text-purple-300 font-medium mb-2">PDF 감정평가서 업로드</h3>
                  <p className="text-gray-400 text-sm">
                    감정평가서 PDF를 업로드하면 자동으로 각 페이지를 이미지로 변환하고,
                    AI가 내용을 분석하여 나레이션 스크립트를 생성합니다.
                    생성된 영상은 슬라이드쇼 형식으로 제작됩니다.
                  </p>
                </div>

                {/* File Input */}
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  PDF 파일 선택
                </label>
                <div className="relative">
                  <input
                    id="pdf-upload"
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={handlePdfSelect}
                    className="hidden"
                  />
                  <label
                    htmlFor="pdf-upload"
                    className="flex items-center justify-center w-full px-4 py-8 rounded-lg
                             bg-gray-700 border-2 border-dashed border-gray-600
                             hover:border-purple-500 hover:bg-gray-700/70
                             cursor-pointer transition-colors"
                  >
                    <div className="text-center">
                      <div className="text-4xl mb-2">📄</div>
                      {pdfFile ? (
                        <div>
                          <p className="text-purple-400 font-medium">{pdfFile.name}</p>
                          <p className="text-gray-500 text-sm mt-1">
                            {(pdfFile.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                      ) : (
                        <div>
                          <p className="text-gray-300">클릭하여 PDF 파일 선택</p>
                          <p className="text-gray-500 text-sm mt-1">
                            또는 파일을 여기에 드래그하세요
                          </p>
                        </div>
                      )}
                    </div>
                  </label>
                </div>
              </div>

              {/* Requirements Notice */}
              <div className="bg-green-900/30 border border-green-700 rounded-lg p-4 mb-6">
                <h4 className="text-green-300 font-medium mb-2">필요 조건</h4>
                <ul className="text-gray-400 text-sm space-y-1">
                  <li>• Anthropic API 키 (Claude Vision API 사용)</li>
                  <li>• <span className="text-green-400">TTS: Edge TTS 무료 사용 (API 키 불필요)</span></li>
                  <li>• PDF 파일 크기: 최대 50MB 권장</li>
                </ul>
              </div>

              {/* Submit Button */}
              <button
                onClick={submitPdfJob}
                disabled={loading || !pdfFile || !!(currentJob && currentJob.status === "processing")}
                className="w-full py-3 px-6 rounded-lg bg-purple-600 hover:bg-purple-700
                         disabled:bg-gray-600 disabled:cursor-not-allowed
                         font-semibold transition-colors"
              >
                {loading ? "업로드 중..." : "PDF 영상 생성하기"}
              </button>
            </>
          )}

          {error && (
            <div className="mt-4 p-4 rounded-lg bg-red-900/50 border border-red-700 text-red-200">
              {error}
            </div>
          )}
        </div>

        {/* Job Status */}
        {currentJob && (
          <div className="bg-gray-800 rounded-xl p-6 mb-8 shadow-xl">
            <h2 className="text-xl font-semibold mb-4">작업 상태</h2>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">작업 ID:</span>
                <span className="font-mono">{currentJob.job_id}</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-400">상태:</span>
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    currentJob.status === "completed"
                      ? "bg-green-900/50 text-green-300"
                      : currentJob.status === "failed"
                      ? "bg-red-900/50 text-red-300"
                      : currentJob.status === "processing"
                      ? "bg-blue-900/50 text-blue-300"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  {statusMap[currentJob.status] || currentJob.status}
                </span>
              </div>

              {currentJob.current_step && (
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">현재 단계:</span>
                  <span>{currentJob.current_step}</span>
                </div>
              )}

              {/* Progress Bar */}
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-gray-400">진행률:</span>
                  <span>{currentJob.progress}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3">
                  <div
                    className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                    style={{ width: `${currentJob.progress}%` }}
                  />
                </div>
              </div>

              {currentJob.error && (
                <div className="p-4 rounded-lg bg-red-900/50 border border-red-700 text-red-200">
                  오류: {currentJob.error}
                </div>
              )}

              {currentJob.video_url && (
                <div className="mt-4">
                  <a
                    href={`${API_URL}${currentJob.video_url}`}
                    download
                    className="inline-block px-6 py-3 rounded-lg bg-green-600 hover:bg-green-700
                             font-semibold transition-colors"
                  >
                    영상 다운로드
                  </a>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Property List */}
        <div className="bg-gray-800 rounded-xl p-6 shadow-xl">
          <h2 className="text-xl font-semibold mb-4">
            매물 목록 ({inputMode === "mock" ? "테스트" : "JSON"})
          </h2>

          {properties.length === 0 ? (
            <p className="text-gray-400">매물이 없습니다</p>
          ) : (
            <div className="space-y-3">
              {properties.map((prop) => (
                <div
                  key={prop.case_number}
                  onClick={() => selectProperty(prop)}
                  className="p-4 rounded-lg bg-gray-700/50 hover:bg-gray-700
                           cursor-pointer transition-colors border border-gray-600"
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-mono text-sm text-blue-400">
                      {prop.case_number}
                    </span>
                    <span className="text-sm text-gray-400">{prop.court}</span>
                  </div>
                  <div className="text-sm mb-2">{prop.address}</div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">
                      감정가: {formatPrice(prop.appraisal_value)}
                    </span>
                    <span className="text-green-400">
                      최저가: {formatPrice(prop.minimum_bid)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="mt-12 text-center text-gray-500 text-sm">
          <p>공매 영상 생성기 v0.1.0</p>
          <p className="mt-1">
            백엔드: Railway | 프론트엔드: Vercel
          </p>
        </footer>
      </div>
    </div>
  );
}
