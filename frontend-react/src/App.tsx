import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  LayoutDashboard,
  BriefcaseBusiness,
  FileUser,
  Settings,
  Users,
  Target,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Download,
  GitCompareArrows,
  ChartNoAxesCombined,
  X,
  FileText,
} from 'lucide-react'

import './App.css'

interface Job {
  id: number
  title: string
  description?: string
  requirements?: {
    required_skills?: string[]
    preferred_skills?: string[]
  }
}

interface Candidate {
  id?: number
  candidate_id?: number
  name?: string
  filename?: string
  score?: number
  match_score?: number
  provisional_score?: number
  rank?: number
  score_status?: string
  evidence_coverage?: number

  profile?: {
    [key: string]: any
  }

  explanation?: {
    [key: string]: any
  }

  [key: string]: any
}
interface ResumeUploadResult {
  filename: string;
  status: 'processed' | 'success' | 'duplicate' | 'failed';
  candidate_id?: number;
  score?: number;
  name?: string;
  error?: string;
}
function getCandidatesArray(data: any): Candidate[] {
  if (Array.isArray(data)) return data

  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data?.candidates)) return data.candidates
  if (Array.isArray(data?.items)) return data.items

  return []
}

function getScore(candidate: Candidate): number | null {
  const value =
    candidate.score ??
    candidate.match_score ??
    candidate.provisional_score

  return typeof value === 'number' ? value : null
}

function RankingExplanationView({ data }: { data: any }) {
  const explanations = Array.isArray(data?.ranking_explanations)
    ? data.ranking_explanations
    : [];

  const componentLabels: Record<string, string> = {
    required_skills: 'Required Skills',
    semantic_relevance: 'Semantic Relevance',
    experience: 'Experience',
    education: 'Education',
    preferred_skills: 'Preferred Skills',
  };

  return (
    <div className="ranking-report">

      <div className="ranking-report-header">
        <div>
          <span className="report-eyebrow">TALENTIQ ANALYSIS</span>
          <h2>Candidate Ranking Analysis</h2>
          <p>Evidence-based comparison of candidates for this role.</p>
        </div>

        <div className="report-count">
          <strong>{data?.candidate_count ?? explanations.length}</strong>
          <span>Candidates</span>
        </div>
      </div>

      <div className="ranking-candidate-list">
        {explanations.map((candidate: any, index: number) => {
          const components = candidate.component_scores || {};
          const evidence = candidate.evidence_summary || {};

          return (
            <div className="ranking-candidate-card" key={candidate.candidate_id ?? index}>

              <div className="ranking-candidate-top">
                <div className="ranking-identity">
                  <div className="ranking-position">
                    #{candidate.rank ?? index + 1}
                  </div>

                  <div>
                    <h3>{candidate.name || 'Unnamed Candidate'}</h3>
                    <span>Candidate ID: {candidate.candidate_id ?? 'N/A'}</span>
                  </div>
                </div>

                <div className="ranking-score">
                  <strong>
                    {Number(candidate.score ?? 0).toFixed(1)}%
                  </strong>
                  <span>Overall Match</span>
                </div>
              </div>

              <div className="ranking-components">
                <h4>Scoring Breakdown</h4>

                {Object.entries(componentLabels).map(([key, label]) => {
                  const value = Number(components[key] ?? 0);

                  return (
                    <div className="ranking-component" key={key}>
                      <div className="ranking-component-heading">
                        <span>{label}</span>
                        <strong>{value.toFixed(1)}%</strong>
                      </div>

                      <div className="ranking-track">
                        <div
                          className="ranking-fill"
                          style={{
                            width: `${Math.min(100, Math.max(0, value))}%`,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="ranking-evidence">
                <h4>Resume Evidence Summary</h4>

                <div className="evidence-grid">
                  <div>
                    <strong>{evidence.matched ?? 0}</strong>
                    <span>Matched</span>
                  </div>

                  <div>
                    <strong>{evidence.related ?? 0}</strong>
                    <span>Related</span>
                  </div>

                  <div>
                    <strong>{evidence.needs_verification ?? 0}</strong>
                    <span>Needs Verification</span>
                  </div>

                  <div>
                    <strong>{evidence.missing ?? 0}</strong>
                    <span>Missing</span>
                  </div>
                </div>
              </div>

              <div className="ranking-comparison">
                <h4>Ranking Comparison</h4>

                <p>
                  {candidate.comparison_to_previous ||
                    'No comparison information available.'}
                </p>

                {candidate.score_gap_to_previous !== undefined && (
                  <span>
                    Score difference: {' '}
                    {Number(candidate.score_gap_to_previous).toFixed(2)} points
                  </span>
                )}
              </div>

              {candidate.interpretation && (
                <div className="ranking-interpretation">
                  <h4>TalentIQ Interpretation</h4>
                  <p>{candidate.interpretation}</p>
                </div>
              )}

            </div>
          );
        })}
      </div>

      <div className="ranking-disclaimer">
        Ranking scores are decision-support signals based on available resume
        evidence. They are not independent proof of candidate quality or
        future job performance.
      </div>

    </div>
  );
}
function App() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJob, setSelectedJob] = useState('')
  const [activePage, setActivePage] = useState<
  'overview' | 'jobs' | 'resumes' | 'settings'
>('overview')

  const [jobTitle, setJobTitle] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [jobCreating, setJobCreating] = useState(false)
  const [jobMessage, setJobMessage] = useState('') 
  const [analyzedJob, setAnalyzedJob] = useState<any | null>(null)
  const analysisResultsRef = useRef<HTMLDivElement>(null)
  

  // ======================================
  // RESUME PROCESSING STATE
  // ======================================

  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadResults, setUploadResults] = useState<ResumeUploadResult[]>([])
  const [uploadMessage, setUploadMessage] = useState('')
  const [dragActive, setDragActive] = useState(false)

  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [selectedCandidates, setSelectedCandidates] = useState<number[]>([])

  const [activeCandidate, setActiveCandidate] =
    useState<Candidate | null>(null)

  const [modalTitle, setModalTitle] = useState('')
  const [modalData, setModalData] = useState<any>(null)

  const [jobsLoading, setJobsLoading] = useState(true)
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  const [error, setError] = useState('')
  const [candidateError, setCandidateError] = useState('')

  const [reloadToken, setReloadToken] = useState(0)

  // --------------------------------
  // LOAD JOBS
  // --------------------------------

  useEffect(() => {
    async function loadJobs() {
      try {
        setJobsLoading(true)
        setError('')

        const response = await fetch('/api/jobs')

        if (!response.ok) {
          throw new Error('Unable to load job descriptions.')
        }

        const data = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('Unexpected jobs API response.')
        }

        setJobs(data)

        if (data.length > 0) {
          setSelectedJob(String(data[0].id))
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to connect to backend.'
        )
      } finally {
        setJobsLoading(false)
      }
    }

    loadJobs()
  }, [])

  // --------------------------------
  // LOAD CANDIDATES
  // --------------------------------

  useEffect(() => {
    if (!selectedJob) {
      setCandidates([])
      return
    }

    const controller = new AbortController()

    async function loadCandidates() {
      try {
        setCandidatesLoading(true)
        setCandidateError('')
        setCandidates([])
        setSelectedCandidates([])

        const response = await fetch(
          `/api/matching/results/${selectedJob}`,
          { signal: controller.signal }
        )

        if (!response.ok) {
          throw new Error('Unable to load candidate results.')
        }

        const data = await response.json()

        console.log('Candidate API response:', data)

        const list = getCandidatesArray(data)

        console.log('Candidate count:', list.length)

        setCandidates(list)
      } catch (err) {
        if (
          err instanceof Error &&
          err.name === 'AbortError'
        ) {
          return
        }

        setCandidateError(
          err instanceof Error
            ? err.message
            : 'Unable to load candidates.'
        )
      } finally {
        if (!controller.signal.aborted) {
          setCandidatesLoading(false)
        }
      }
    }

    loadCandidates()

    return () => controller.abort()
  }, [selectedJob, reloadToken])

  // --------------------------------
  // STATISTICS
  // --------------------------------

  const statistics = useMemo(() => {
    const scores = candidates
      .map(getScore)
      .filter((score): score is number => score !== null)

    const average =
      scores.length > 0
        ? scores.reduce((sum, score) => sum + score, 0) /
          scores.length
        : null

    const strongMatches = scores.filter(
      score => score >= 75
    ).length

    const fullyEvaluated = candidates.filter(candidate => {
      const status = String(
        candidate.score_status || ''
      ).toLowerCase()

      return (
        status === 'complete' ||
        status === 'fully_evaluated'
      )
    }).length

    const coverage = candidates
      .map(candidate => candidate.evidence_coverage)
      .filter(
        (value): value is number =>
          typeof value === 'number'
      )

    const averageCoverage =
      coverage.length > 0
        ? coverage.reduce((sum, value) => sum + value, 0) /
          coverage.length
        : null

    return {
      total: candidates.length,
      average,
      strongMatches,
      fullyEvaluated,
      scored: scores.length,
      averageCoverage,
    }
  }, [candidates])

  const selectedJobDetails = jobs.find(
    job => String(job.id) === selectedJob
  )

  const sortedCandidates = useMemo(() => {
    return [...candidates].sort((a, b) => {
      const scoreA = getScore(a) ?? -1
      const scoreB = getScore(b) ?? -1

      return scoreB - scoreA
    })
  }, [candidates])

  const formatScore = (score: number | null) => {
    return score === null ? '—' : `${score.toFixed(1)}%`
  }

  // --------------------------------
  // SELECT CANDIDATES
  // --------------------------------

  const toggleCandidate = (candidate: Candidate) => {
    const id = candidate.id ?? candidate.candidate_id

    if (typeof id !== 'number') {
      alert('Candidate ID is unavailable.')
      return
    }

    setSelectedCandidates(previous =>
      previous.includes(id)
        ? previous.filter(item => item !== id)
        : [...previous, id]
    )
  }

  // --------------------------------
  // CANDIDATE PROFILE
  // --------------------------------

  const openCandidate = (candidate: Candidate) => {
  console.log('CANDIDATE EVALUATION DATA:', candidate)
  setActiveCandidate(candidate)
}
  // ======================================
  // CREATE AND ANALYZE JOB DESCRIPTION
  // ======================================

  const handleCreateJob = async () => {
  if (!jobTitle.trim() || !jobDescription.trim()) {
    setJobMessage('Please enter a job title and description.');
    return;
  }

  try {
    setJobCreating(true);
    setJobMessage('');

    const response = await fetch('/api/jobs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: jobTitle,
        description: jobDescription,
      }),
    });

    const createdJob = await response.json();

    if (!response.ok) {
      throw new Error(
        createdJob.detail || 'Unable to analyze job description.'
      );
    }

    // Preserve the analyzed job for immediate display.
    setAnalyzedJob(createdJob);

    // Scroll to the analysis results after they render.
    setTimeout(() => {
      analysisResultsRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }, 150);

    // Refresh saved jobs.
    const jobsResponse = await fetch('/api/jobs');

    if (!jobsResponse.ok) {
      throw new Error('Job created, but the saved jobs list could not refresh.');
    }

    const updatedJobs = await jobsResponse.json();

    setJobs(updatedJobs);

    setSelectedJob(String(createdJob.id));

    setJobMessage('Job description analyzed and saved successfully.');

    setJobTitle('');
    setJobDescription('');

  } catch (error: any) {
    setJobMessage(
      error.message || 'Something went wrong while analyzing the job.'
    );
  } finally {
    setJobCreating(false);
  }
};


  // ======================================
  // RESUME FILE SELECTION
  // ======================================

  const handleFileSelection = (fileList: FileList | null) => {
    if (!fileList) return

    const allowedExtensions = ['pdf', 'docx']

    const incomingFiles = Array.from(fileList)

    const validFiles: File[] = []
    const errors: string[] = []

    incomingFiles.forEach(file => {

      const extension = file.name
        .split('.')
        .pop()
        ?.toLowerCase()

      if (!extension || !allowedExtensions.includes(extension)) {
        errors.push(
          `${file.name}: Only PDF and DOCX files are allowed.`
        )
        return
      }

      if (file.size > 8 * 1024 * 1024) {
        errors.push(
          `${file.name}: File exceeds the 8 MB limit.`
        )
        return
      }

      validFiles.push(file)

    })

    setSelectedFiles(previous => {

      const combined = [...previous, ...validFiles]

      return combined.filter(
        (file, index, array) =>
          array.findIndex(
            item =>
              item.name === file.name &&
              item.size === file.size &&
              item.lastModified === file.lastModified
          ) === index
      )

    })

    setUploadMessage(errors.join('\n'))
  }


  // ======================================
  // REMOVE SELECTED FILE
  // ======================================

  const removeSelectedFile = (index: number) => {

    setSelectedFiles(previous =>
      previous.filter(
        (_, fileIndex) => fileIndex !== index
      )
    )

  }


  // ======================================
  // UPLOAD AND PROCESS RESUMES
  // ======================================

  const handleResumeUpload = async () => {

    if (!selectedJob) {
      setUploadMessage(
        'Please select a job description first.'
      )
      return
    }

    if (selectedFiles.length === 0) {
      setUploadMessage(
        'Please select at least one resume.'
      )
      return
    }

    try {

      setUploading(true)

      setUploadMessage(
        'Uploading and processing resumes...'
      )

      setUploadResults([])

      const formData = new FormData()

      selectedFiles.forEach(file => {
        formData.append('files', file)
      })

      const response = await fetch(
        `/api/resumes/upload?job_id=${encodeURIComponent(selectedJob)}`,
        {
          method: 'POST',
          body: formData,
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail || 'Resume upload failed.'
        )
      }

      const results: ResumeUploadResult[] = Array.isArray(data.results)
        ? data.results
        : []

      setUploadResults(results)

      const processed = results.filter(
        item =>
          item.status === 'processed' ||
          item.status === 'success'
      ).length

      const duplicates = results.filter(
        item => item.status === 'duplicate'
      ).length

      const failed = results.filter(
        item => item.status === 'failed'
      ).length

      setUploadMessage(
        `${processed} processed · ${duplicates} duplicates · ${failed} failed`
      )

      setSelectedFiles([])

      // Refresh candidate data
      setReloadToken(previous => previous + 1)

    } catch (error) {

      setUploadMessage(
        error instanceof Error
          ? error.message
          : 'Something went wrong during upload.'
      )

    } finally {

      setUploading(false)

    }

  }

  // --------------------------------
  // COMPARE CANDIDATES
  // --------------------------------

  const handleCompare = async () => {
    if (selectedCandidates.length < 2) {
      alert('Select at least two candidates.')
      return
    }

    try {
      setActionLoading(true)

      const response = await fetch(
        '/api/candidates/compare',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            candidate_ids: selectedCandidates,
          }),
        }
      )

      if (!response.ok) {
        throw new Error('Candidate comparison failed.')
      }

      const data = await response.json()

      setModalTitle('Candidate Comparison')
      setModalData(data)
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : 'Comparison failed.'
      )
    } finally {
      setActionLoading(false)
    }
  }

  // --------------------------------
  // EXPLAIN RANKING
  // --------------------------------

  const handleExplainRanking = async () => {
    if (!selectedJob) return

    try {
      setActionLoading(true)

      const response = await fetch(
        `/api/jobs/${selectedJob}/ranking/explanation`
      )

      if (!response.ok) {
        throw new Error('Unable to explain ranking.')
      }

      const data = await response.json()

      setModalTitle('Ranking Explanation')
      setModalData(data)
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : 'Request failed.'
      )
    } finally {
      setActionLoading(false)
    }
  }

  // --------------------------------
  // RECALCULATE SCORES
  // --------------------------------

  const handleRecalculate = async () => {
    if (!selectedJob) return

    const confirmed = window.confirm(
      'Recalculate scores for this role?'
    )

    if (!confirmed) return

    try {
      setActionLoading(true)

      const response = await fetch(
        `/api/jobs/${selectedJob}/recalculate`,
        { method: 'POST' }
      )

      if (!response.ok) {
        throw new Error('Recalculation failed.')
      }

      setSelectedCandidates([])
      setReloadToken(previous => previous + 1)

      alert('Scores recalculated successfully.')
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : 'Recalculation failed.'
      )
    } finally {
      setActionLoading(false)
    }
  }

  // --------------------------------
  // EXPORT CSV
  // --------------------------------

  const handleExport = () => {
    if (!selectedJob) return

    window.location.href =
      `/api/candidates/export/${selectedJob}`
  }

  // --------------------------------
  // CLOSE MODALS
  // --------------------------------

  const closeModals = () => {
    setActiveCandidate(null)
    setModalData(null)
  }

  // --------------------------------
  // MAIN UI
  // --------------------------------

  return (
    <div className="app">

      {/* SIDEBAR */}

      <aside className="sidebar">

        {/* TALENTIQ BRAND */}

<div className="brand-logo">
  <div className="brand-icon">
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M24 5C15.2 5 8 12.2 8 21C8 28.1 12.6 34.1 19 36.2V42H29V36.2C35.4 34.1 40 28.1 40 21C40 12.2 32.8 5 24 5Z"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinejoin="round"
      />

      <circle cx="18" cy="19" r="2.5" fill="#72A5FF" />
      <circle cx="30" cy="16" r="2.5" fill="#72A5FF" />
      <circle cx="25" cy="27" r="2.5" fill="#72A5FF" />
      <circle cx="16" cy="29" r="2" fill="#72A5FF" />

      <path
        d="M18 19L25 27L30 16M18 19L16 29M16 29L25 27"
        stroke="#72A5FF"
        strokeWidth="1.7"
        strokeLinecap="round"
      />

      <path
        d="M19 42H29"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  </div>

  <div className="brand-text">
    <div className="brand-name">
      Talent<span>IQ</span>
    </div>

    <div className="brand-tagline">
      AI-POWERED TALENT DISCOVERY
    </div>
  </div>
</div>
        

        <nav>
  <a
    className={activePage === 'overview' ? 'active' : ''}
    onClick={() => setActivePage('overview')}
  >
    <LayoutDashboard size={17} />
    Candidate Intelligence
  </a>

  <a
    className={activePage === 'jobs' ? 'active' : ''}
    onClick={() => setActivePage('jobs')}
  >
    <BriefcaseBusiness size={17} />
    Job Descriptions
  </a>

  <a
    className={activePage === 'resumes' ? 'active' : ''}
    onClick={() => setActivePage('resumes')}
  >
    <FileUser size={17} />
    Resume Processing
  </a>

  <a
    className={activePage === 'settings' ? 'active' : ''}
    onClick={() => setActivePage('settings')}
  >
    <Settings size={17} />
    Settings
  </a>
</nav>

        <div className="sidebar-footer">
          Evidence-based hiring
          <br />
          Local workspace
        </div>

      </aside>

      {/* MAIN CONTENT */}

      <main className="main">
        {activePage === 'overview' && (
  <>

        {/* HEADER */}

        <header className="header">

          <div>
            <p className="eyebrow">
              RECRUITMENT INTELLIGENCE
            </p>

            <h1>Candidate Overview</h1>
          </div>

          <select
            value={selectedJob}
            onChange={event =>
              setSelectedJob(event.target.value)
            }
            disabled={jobsLoading}
          >
            <option value="">
              {jobsLoading
                ? 'Loading roles...'
                : 'Select a role'}
            </option>

            {jobs.map(job => (
              <option
                key={job.id}
                value={String(job.id)}
              >
                {job.title}
              </option>
            ))}
          </select>

        </header>

        {error && (
          <div className="error">
            {error}
          </div>
        )}

        {/* SELECTED ROLE */}

        {selectedJobDetails && (
          <div className="selected-job">
            <BriefcaseBusiness size={17} />

            <span>
              Showing candidates for{' '}
              <strong>
                {selectedJobDetails.title}
              </strong>
            </span>
          </div>
        )}

        {/* STATISTICS */}

        <section className="stats">

          <StatCard
            icon={<Users size={18} />}
            title="Total Candidates"
            value={
              candidatesLoading
                ? '...'
                : String(statistics.total)
            }
            subtitle="Candidates analyzed"
          />

          <StatCard
            icon={<Target size={18} />}
            title="Average Match"
            value={formatScore(statistics.average)}
            subtitle={`${statistics.scored} scored candidates`}
          />

          <StatCard
            icon={<CheckCircle2 size={18} />}
            title="Strong Matches"
            value={String(statistics.strongMatches)}
            subtitle="Score ≥ 75%"
          />

          <StatCard
            icon={<AlertCircle size={18} />}
            title="Processing Issues"
            value={String(
              candidates.filter(candidate =>
                String(candidate.score_status || '')
                  .toLowerCase()
                  .includes('error')
              ).length
            )}
            subtitle="Reported candidate errors"
          />

          <StatCard
            icon={<CheckCircle2 size={18} />}
            title="Fully Evaluated"
            value={`${statistics.fullyEvaluated}/${statistics.total}`}
            subtitle="Based on evaluation status"
          />

          <StatCard
            icon={<ChartNoAxesCombined size={18} />}
            title="Evidence Coverage"
            value={formatScore(statistics.averageCoverage)}
            subtitle="Average available coverage"
          />

        </section>

        {/* CANDIDATE RANKING */}

        <section className="panel">

          <div className="panel-heading">

            <div>
              <h3>Candidate Ranking</h3>

              <p>
                Evidence-backed candidate matching and ranking.
                Scores are decision-support signals, not hiring decisions.
              </p>
            </div>

            <div className="actions">

              <button
                onClick={handleCompare}
                disabled={
                  selectedCandidates.length < 2 ||
                  actionLoading
                }
              >
                <GitCompareArrows size={15} />

                Compare ({selectedCandidates.length})
              </button>

              <button
                onClick={handleExplainRanking}
                disabled={!selectedJob || actionLoading}
              >
                Explain Ranking
              </button>

              <button
                onClick={handleRecalculate}
                disabled={!selectedJob || actionLoading}
              >
                <RefreshCw size={15} />

                {actionLoading
                  ? 'Processing...'
                  : 'Recalculate'}
              </button>

              <button
                onClick={handleExport}
                disabled={!selectedJob}
              >
                <Download size={15} />
                Export CSV
              </button>

            </div>

          </div>

          {candidateError && (
            <div className="error">
              {candidateError}
            </div>
          )}

          <div className="table-wrap">

            <table>

              <thead>
                <tr>
                  <th>SELECT</th>
                  <th>RANK</th>
                  <th>CANDIDATE</th>
                  <th>MATCH</th>
                  <th>EVALUATION</th>
                  <th>EXPERIENCE</th>
                  <th>REQUIRED SKILLS</th>
                  <th>MISSING / UNVERIFIED</th>
                </tr>
              </thead>

              <tbody>

                {candidatesLoading ? (
                  <tr>
                    <td colSpan={8} className="empty">
                      Loading candidate results...
                    </td>
                  </tr>
                ) : sortedCandidates.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="empty">
                      No candidates analyzed for this role yet.
                    </td>
                  </tr>
                ) : (

                  sortedCandidates.map((candidate, index) => {

                    const id =
                      candidate.id ??
                      candidate.candidate_id

                    const score = getScore(candidate)

                    const satisfied =
                      candidate.explanation?.satisfied || []

                    const missing =
                      candidate.explanation?.missing_skills || []

                    const unverified =
                      candidate.explanation?.not_verified || []

                    const analysis =
                      candidate.explanation?.required_skill_analysis || []

                    const experience =
                      candidate.profile?.total_experience_years

                    return (

                      <tr
                        key={id ?? candidate.filename ?? index}
                        className="candidate-row"
                        onClick={() => openCandidate(candidate)}
                      >

                        <td>
                          <input
                            type="checkbox"
                            checked={
                              typeof id === 'number' &&
                              selectedCandidates.includes(id)
                            }
                            disabled={typeof id !== 'number'}
                            onClick={event =>
                              event.stopPropagation()
                            }
                            onChange={() =>
                              toggleCandidate(candidate)
                            }
                          />
                        </td>

                        <td>
                          #{candidate.rank ?? index + 1}
                        </td>

                        <td>
                          <button
                            className="candidate-name"
                            onClick={event => {
                              event.stopPropagation()
                              openCandidate(candidate)
                            }}
                          >
                            {candidate.name ||
                              candidate.filename ||
                              `Candidate ${index + 1}`}
                          </button>
                        </td>

                        <td>
                          <span className="score">
                            {formatScore(score)}
                          </span>
                        </td>

                        <td>
                          <span className="status">
                            {candidate.score_status || '—'}
                          </span>
                        </td>

                        <td>
                          {typeof experience === 'number'
                            ? `${experience} years`
                            : candidate.profile?.experience_type || '—'}
                        </td>

                        <td>
                          {analysis.length > 0
                            ? `${analysis.length} analyzed`
                            : satisfied.length > 0
                              ? `${satisfied.length} evidenced`
                              : '—'}
                        </td>

                        <td>
                          {missing.length + unverified.length > 0
                            ? `${missing.length} missing, ${unverified.length} unverified`
                            : '—'}
                        </td>

                      </tr>

                    )
                  })

                )}

              </tbody>

            </table>

          </div>

        </section>

        {/* LOWER DASHBOARD */}

        <section className="bottom-grid">

          <div className="panel">

            <h3>Match Score Distribution</h3>

            <p>
              Current candidate set
            </p>

            <div className="distribution">

              {[0, 20, 40, 60, 80].map(minimum => {

                const maximum = minimum + 19

                const count = candidates.filter(candidate => {
                  const score = getScore(candidate)

                  return (
                    score !== null &&
                    score >= minimum &&
                    score <= maximum
                  )
                }).length

                return (
                  <div
                    className="distribution-item"
                    key={minimum}
                  >

                    <span>
                      {minimum}–{maximum}%: {count}
                    </span>

                    <div className="distribution-bar">
                      <div
                        style={{
                          width:
                            statistics.total > 0
                              ? `${(count / statistics.total) * 100}%`
                              : '0%',
                        }}
                      />
                    </div>

                  </div>
                )
              })}

            </div>

          </div>

          <div className="panel">

            <h3>Recent Processing Activity</h3>

            <p>
              {candidates.length > 0
                ? `${candidates.length} candidate records available.`
                : 'No candidate records available.'}
            </p>

          </div>

          <div className="panel">

            <h3>Hiring Signal Overview</h3>

            <p>
              Evidence-backed candidate information.
            </p>

            <p>
              {statistics.scored} candidates have an available score.
            </p>

          </div>

          <div className="panel">

            <h3>Required Skill Coverage</h3>

            <p>
              Required skills for the selected role.
            </p>

            {selectedJobDetails?.requirements?.required_skills?.length ? (

              <div className="skill-list">

                {selectedJobDetails.requirements.required_skills.map(
                  skill => (
                    <span
                      className="skill-tag"
                      key={skill}
                    >
                      {skill}
                    </span>
                  )
                )}

              </div>

            ) : (
              <p>No required skills available.</p>
            )}

          </div>

        </section>

          </>
)}

{/* ======================================
    JOB DESCRIPTIONS PAGE
====================================== */}

{activePage === 'jobs' && (
  <div className="page-content">

    <header className="page-header">
      <div>
        <p className="eyebrow">
          RECRUITMENT INTELLIGENCE
        </p>

        <h1>Job Descriptions</h1>

        <p>
          Create roles and extract structured hiring requirements.
        </p>
      </div>
    </header>

    {/* CREATE JOB */}

    <section className="panel job-form-panel">

      <div className="section-title">
        <h3>Create New Job</h3>

        <p>
          Paste a job description to extract skills and requirements.
        </p>
      </div>

      <div className="job-form">

        <div className="form-group">
          <label>Job Title</label>

          <input
            type="text"
            className="job-input"
            placeholder="e.g. AI/ML Engineer Intern"
            value={jobTitle}
            onChange={event =>
              setJobTitle(event.target.value)
            }
          />
        </div>

        <div className="form-group">
          <label>Job Description *</label>

          <textarea
            className="job-textarea"
            placeholder="Paste the complete job description here..."
            value={jobDescription}
            onChange={event =>
              setJobDescription(event.target.value)
            }
            rows={10}
          />
        </div>

        <button
          className="primary-action"
          onClick={handleCreateJob}
          disabled={jobCreating}
        >
          {jobCreating
            ? 'Analyzing...'
            : 'Analyze Job Description'}
        </button>

        {jobMessage && (
          <div className="form-message">
            {jobMessage}
          </div>
        )}

      </div>

    </section>

    {/* JOB ANALYSIS RESULTS */}

    {analyzedJob && (
      <div
        className="panel analyzed-job-panel"
        ref={analysisResultsRef}
      >
        <div className="section-title">
          <div>
            <span className="report-eyebrow">
              TALENTIQ JOB INTELLIGENCE
            </span>

            <h3>Job Analysis Results</h3>

            <p>
              Extracted hiring requirements for {analyzedJob.title}
            </p>
          </div>

          <span className="analysis-success-badge">
            ✓ Analysis Complete
          </span>
        </div>

        <div className="analysis-description">
          <h4>Job Description</h4>
          <p>{analyzedJob.description}</p>
        </div>

        <div className="analysis-skills-grid">
          <div className="analysis-skill-group">
            <h4>Required Skills</h4>

            <div className="analysis-tags">
              {(analyzedJob.requirements?.required_skills || []).map(
                (skill: string, index: number) => (
                  <span key={index}>{skill}</span>
                )
              )}
            </div>
          </div>

          <div className="analysis-skill-group">
            <h4>Preferred Skills</h4>

            <div className="analysis-tags">
              {(analyzedJob.requirements?.preferred_skills || []).map(
                (skill: string, index: number) => (
                  <span key={index}>{skill}</span>
                )
              )}
            </div>
          </div>
        </div>

        <div className="analysis-footer">
          <span>
            {(analyzedJob.requirements?.required_skills || []).length}
            {' '}required skills extracted
          </span>

          <button
            className="secondary-action"
            onClick={() => {
              setSelectedJob(String(analyzedJob.id));
              setActivePage('overview');
            }}
          >
            View Candidates
          </button>
        </div>
      </div>
    )}

    {/* EXISTING JOBS */}

    <section className="panel">

      <div className="section-title">
        <h3>Existing Job Descriptions</h3>

        <p>
          Select a role to view its candidate rankings.
        </p>
      </div>

      {jobsLoading ? (
        <p>Loading job descriptions...</p>
      ) : jobs.length === 0 ? (
        <div className="empty">
          No job descriptions created yet.
        </div>
      ) : (

        <div className="job-list">

          {jobs.map(job => (

            <div className="job-card" key={job.id}>

              <div className="job-card-info">

                <h3>{job.title}</h3>

                <p>
                  {job.requirements?.required_skills?.length || 0}
                  {' '}required skills extracted
                </p>

                <div className="skill-list">

                  {job.requirements?.required_skills?.slice(0, 5).map(
                    skill => (
                      <span className="skill-tag" key={skill}>
                        {skill}
                      </span>
                    )
                  )}

                </div>

              </div>

              <button
                className="secondary-action"
                onClick={() => {
                  setSelectedJob(String(job.id))
                  setActivePage('overview')
                }}
              >
                View Candidates
              </button>

            </div>

          ))}

        </div>

      )}

    </section>

  </div>
)}

{/* ======================================
    RESUME PROCESSING PAGE
====================================== */}

{activePage === 'resumes' && (

  <div className="page-content">

    <header className="page-header">

      <div>

        <p className="eyebrow">
          RECRUITMENT INTELLIGENCE
        </p>

        <h1>Resume Processing</h1>

        <p>
          Upload and analyze candidate resumes against job requirements.
        </p>

      </div>

      <select
        value={selectedJob}
        onChange={event => {
          setSelectedJob(event.target.value)
          setUploadResults([])
          setUploadMessage('')
        }}
      >

        <option value="">
          Select a job
        </option>

        {jobs.map(job => (
          <option
            key={job.id}
            value={String(job.id)}
          >
            {job.title}
          </option>
        ))}

      </select>

    </header>


    {!selectedJob && (

      <div className="error">
        Please create or select a job description before uploading resumes.
      </div>

    )}


    {/* UPLOAD PANEL */}

    <section className="panel">

      <div className="section-title">

        <h3>Upload Resumes</h3>

        <p>
          Upload multiple PDF or DOCX resumes for automated evaluation.
        </p>

      </div>


      {/* DROPZONE */}

      <div
        className={`resume-dropzone ${
          dragActive ? 'drag-active' : ''
        }`}

        onDragOver={event => {
          event.preventDefault()
          setDragActive(true)
        }}

        onDragLeave={() => {
          setDragActive(false)
        }}

        onDrop={event => {
          event.preventDefault()
          setDragActive(false)
          handleFileSelection(event.dataTransfer.files)
        }}
      >

        <FileUser size={42} />

        <h3>
          Drag and drop resumes here
        </h3>

        <p>
          Or select files from your computer.
        </p>

        <label className="upload-select-button">

          Browse Files

          <input
            type="file"
            accept=".pdf,.docx"
            multiple
            hidden
            onChange={event => {
              handleFileSelection(event.target.files)
              event.target.value = ''
            }}
          />

        </label>

        <span className="muted">
          PDF and DOCX · Maximum 8 MB per file
        </span>

      </div>


      {/* SELECTED FILES */}

      {selectedFiles.length > 0 && (

        <div className="selected-file-section">

          <div className="section-title">

            <h3>
              Selected Files ({selectedFiles.length})
            </h3>

            <button
              onClick={() => setSelectedFiles([])}
              disabled={uploading}
            >
              Clear All
            </button>

          </div>


          {selectedFiles.map((file, index) => (

            <div
              className="selected-file"
              key={`${file.name}-${index}`}
            >

              <div>

                <FileText size={20} />

                <div>

                  <strong>{file.name}</strong>

                  <p>
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>

                </div>

              </div>


              <button
                onClick={() => removeSelectedFile(index)}
                disabled={uploading}
                aria-label={`Remove ${file.name}`}
              >

                <X size={17} />

              </button>

            </div>

          ))}


          <button
            className="upload-submit-button"
            onClick={handleResumeUpload}
            disabled={
              uploading ||
              !selectedJob ||
              selectedFiles.length === 0
            }
          >

            {uploading
              ? 'Processing Resumes...'
              : `Upload and Analyze ${selectedFiles.length} Resume(s)`}

          </button>

        </div>

      )}


      {uploadMessage && (

        <div className="upload-message">
          {uploadMessage}
        </div>

      )}

    </section>


    {/* PROCESSING RESULTS */}

    {uploadResults.length > 0 && (

      <section className="panel">

        <div className="section-title">

          <h3>Processing Results</h3>

          <p>
            Results returned by the resume processing backend.
          </p>

        </div>


        <div className="upload-result-summary">

          <div>

            <strong>
              {uploadResults.filter(
                item =>
                  item.status === 'processed' ||
                  item.status === 'success'
              ).length}
            </strong>

            <span>Processed</span>

          </div>


          <div>

            <strong>
              {uploadResults.filter(
                item => item.status === 'duplicate'
              ).length}
            </strong>

            <span>Duplicates</span>

          </div>


          <div>

            <strong>
              {uploadResults.filter(
                item => item.status === 'failed'
              ).length}
            </strong>

            <span>Failed</span>

          </div>

        </div>


        <div className="table-wrap">

          <table>

            <thead>

              <tr>
                <th>RESUME</th>
                <th>STATUS</th>
                <th>CANDIDATE</th>
                <th>MATCH SCORE</th>
                <th>DETAILS</th>
              </tr>

            </thead>


            <tbody>

              {uploadResults.map((item, index) => (

                <tr key={`${item.filename}-${index}`}>

                  <td>{item.filename}</td>

                  <td>
                    <span className="status">
                      {item.status}
                    </span>
                  </td>

                  <td>
                    {item.name ||
                      (item.candidate_id
                        ? `Candidate #${item.candidate_id}`
                        : '—')}
                  </td>

                  <td>
                    {typeof item.score === 'number'
                      ? `${item.score.toFixed(1)}%`
                      : '—'}
                  </td>

                  <td>
                    {item.error || '—'}
                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>


        <button
          className="primary-action"
          onClick={() => setActivePage('overview')}
        >
          View Candidate Ranking
        </button>

      </section>

    )}

  </div>

)}

{/* ======================================
    SETTINGS PAGE
====================================== */}

{activePage === 'settings' && (

  <div className="page-content">

    <header className="page-header">

      <div>

        <p className="eyebrow">
          WORKSPACE CONFIGURATION
        </p>

        <h1>Settings</h1>

        <p>
          View TalentIQ configuration and evaluation methodology.
        </p>

      </div>

    </header>


    {/* WORKSPACE INFORMATION */}

    <section className="panel">

      <div className="section-title">

        <h3>Workspace Information</h3>

        <p>
          Current application configuration.
        </p>

      </div>


      <div className="settings-grid">

        <div className="settings-item">

          <span>Application</span>

          <strong>TalentIQ</strong>

        </div>


        <div className="settings-item">

          <span>Platform</span>

          <strong>AI Resume Matching System</strong>

        </div>


        <div className="settings-item">

          <span>Frontend</span>

          <strong>React + TypeScript</strong>

        </div>


        <div className="settings-item">

          <span>Backend</span>

          <strong>FastAPI</strong>

        </div>


        <div className="settings-item">

          <span>Database</span>

          <strong>SQLite</strong>

        </div>


        <div className="settings-item">

          <span>Current Role</span>

          <strong>
            {selectedJobDetails?.title || 'No role selected'}
          </strong>

        </div>

      </div>

    </section>


    {/* RESUME CONFIGURATION */}

    <section className="panel">

      <div className="section-title">

        <h3>Resume Processing Configuration</h3>

        <p>
          Supported file types and upload restrictions.
        </p>

      </div>


      <div className="settings-grid">

        <div className="settings-item">

          <span>Supported Formats</span>

          <strong>PDF, DOCX</strong>

        </div>


        <div className="settings-item">

          <span>Maximum File Size</span>

          <strong>8 MB per file</strong>

        </div>


        <div className="settings-item">

          <span>Batch Upload</span>

          <strong>Multiple Files</strong>

        </div>


        <div className="settings-item">

          <span>Duplicate Detection</span>

          <strong>SHA-256 File Hash</strong>

        </div>


        <div className="settings-item">

          <span>Resume Parsing</span>

          <strong>Enabled through backend</strong>

        </div>


        <div className="settings-item">

          <span>Candidate Evaluation</span>

          <strong>Evidence-based scoring</strong>

        </div>

      </div>

    </section>


    {/* SCORING CONFIGURATION */}

    <section className="panel">

      <div className="section-title">

        <h3>Candidate Scoring Methodology</h3>

        <p>
          Current scoring weights used by the backend evaluation engine.
        </p>

      </div>


      <div className="settings-weight-list">

        {[
          {
            name: 'Required Skills',
            weight: 35,
          },
          {
            name: 'Semantic Relevance',
            weight: 25,
          },
          {
            name: 'Experience',
            weight: 20,
          },
          {
            name: 'Education',
            weight: 10,
          },
          {
            name: 'Preferred Skills',
            weight: 10,
          },
        ].map(item => (

          <div
            className="weight-item"
            key={item.name}
          >

            <div className="weight-heading">

              <strong>{item.name}</strong>

              <span>{item.weight}%</span>

            </div>


            <div className="weight-track">

              <div
                className="weight-fill"
                style={{
                  width: `${item.weight}%`,
                }}
              />

            </div>

          </div>

        ))}

      </div>


      <div className="settings-note">

        <CheckCircle2 size={18} />

        <p>
          These weights are displayed for reference.
          Changes to scoring configuration are not available from this page.
        </p>

      </div>

    </section>


    {/* WORKSPACE STATUS */}

    <section className="panel">

      <div className="section-title">

        <h3>Workspace Overview</h3>

      </div>


      <div className="settings-grid">

        <div className="settings-item">

          <span>Total Job Descriptions</span>

          <strong>{jobs.length}</strong>

        </div>


        <div className="settings-item">

          <span>Selected Job</span>

          <strong>
            {selectedJobDetails?.title || 'None'}
          </strong>

        </div>


        <div className="settings-item">

          <span>Analyzed Candidates</span>

          <strong>{candidates.length}</strong>

        </div>


        <div className="settings-item">

          <span>Scored Candidates</span>

          <strong>{statistics.scored}</strong>

        </div>

      </div>

    </section>

  </div>

)}

      </main>

      {/* CANDIDATE EVALUATION REPORT */}

{activeCandidate && (
  <div className="modal-overlay" onClick={closeModals}>
    <div
      className="modal evaluation-modal"
      onClick={event => event.stopPropagation()}
    >
      {(() => {
        const candidate = activeCandidate
        const explanation = candidate.explanation || {}
        const profile = candidate.profile || {}
        const candidateProfile = profile.candidate || {}

        const requiredSkills =
          explanation.required_skill_analysis || []

        const preferredSkills =
          explanation.preferred_skill_analysis || []

        const projects =
          profile.project_evidence || profile.projects || []

        const internships =
          profile.internship_evidence || []

        const education =
          profile.education || []

        const certifications =
          profile.certifications || []

        const weights = explanation.scoring_weights || {}

        const breakdown = explanation.score_breakdown || {}
        const components = explanation.component_analysis || {}

        const formatValue = (value: any): string => {
          if (value === null || value === undefined) return 'Not available'
          if (typeof value === 'boolean') return value ? 'Yes' : 'No'
          if (typeof value === 'number') return String(value)
          if (typeof value === 'string') return value
          return JSON.stringify(value)
        }

        const renderComponent = (
          title: string,
          key: string
        ) => {
          const data =
            breakdown[key] ?? components[key]

          if (!data || typeof data !== 'object') return null

          const weight = weights[key]

          return (
            <div className="evaluation-component" key={key}>
              <div className="component-heading">
                <div>
                  <h4>{title}</h4>
                  <span>
                    {weight !== undefined
                      ? `${weight}% scoring weight`
                      : 'Evaluation component'}
                  </span>
                </div>

                <strong>
                  {data.score !== null && data.score !== undefined
                    ? `${formatValue(data.score)}${data.score <= 100 ? '%' : ''}`
                    : data.status === 'not_required'
                      ? 'Not required'
                      : 'Not evaluated'}
                </strong>
              </div>

              {data.explanation && (
                <p>{data.explanation}</p>
              )}

              {data.status && (
                <span className="evaluation-status">
                  {formatValue(data.status).replaceAll('_', ' ')}
                </span>
              )}
            </div>
          )
        }

        const renderSkillAnalysis = (
          items: any[],
          emptyText: string
        ) => {
          if (!Array.isArray(items) || items.length === 0) {
            return <p className="muted">{emptyText}</p>
          }

          return (
            <div className="skill-analysis-list">
              {items.map((item: any, index: number) => {
                const skill =
                  item.skill ||
                  item.name ||
                  item.requirement ||
                  item.required_skill ||
                  `Skill ${index + 1}`

                const status = String(
                  item.status || item.match_status || 'evaluated'
                ).replaceAll('_', ' ')

                return (
                  <div className="skill-analysis-item" key={index}>
                    <div className="skill-analysis-heading">
                      <strong>{skill}</strong>
                      <span>{status}</span>
                    </div>

                    {Object.entries(item).map(([key, value]) => {
                      if (
                        ['skill', 'name', 'requirement',
                         'required_skill', 'status', 'match_status'].includes(key) ||
                        value === null ||
                        value === undefined ||
                        typeof value === 'object'
                      ) {
                        return null
                      }

                      return (
                        <div className="skill-evidence-row" key={key}>
                          <span>{key.replaceAll('_', ' ')}</span>
                          <strong>{formatValue(value)}</strong>
                        </div>
                      )
                    })}

                    {Object.entries(item).map(([key, value]) => {
                      if (
                        value === null ||
                        typeof value !== 'object' ||
                        Array.isArray(value)
                      ) {
                        return null
                      }

                      return (
                        <div className="skill-detail" key={key}>
                          <strong>{key.replaceAll('_', ' ')}</strong>

                          {Object.entries(value as object).map(
                            ([subKey, subValue]) => (
                              <div className="skill-evidence-row" key={subKey}>
                                <span>{subKey.replaceAll('_', ' ')}</span>
                                <strong>{formatValue(subValue)}</strong>
                              </div>
                            )
                          )}
                        </div>
                      )
                    })}

                    {Object.entries(item).map(([key, value]) => {
                      if (!Array.isArray(value) || value.length === 0) {
                        return null
                      }

                      return (
                        <div className="skill-detail" key={key}>
                          <strong>{key.replaceAll('_', ' ')}</strong>
                          {value.map((entry: any, i: number) => (
                            <p key={i}>
                              {typeof entry === 'object'
                                ? formatValue(entry)
                                : entry}
                            </p>
                          ))}
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </div>
          )
        }

        return (
          <>
            {/* REPORT HEADER */}

            <div className="evaluation-header">
              <div>
                <p className="eyebrow">TALENTIQ · CANDIDATE INTELLIGENCE</p>
                <h2>{candidate.name || candidate.filename}</h2>
                <p>{candidate.filename || 'Resume'}</p>
              </div>

              <button
                className="close-button"
                onClick={closeModals}
              >
                <X size={20} />
              </button>
            </div>

            {/* OVERALL SCORE */}

            <section className="evaluation-hero">
              <div>
                <span>OVERALL MATCH SCORE</span>
                <h1>{formatScore(getScore(candidate))}</h1>
                <p>
                  {explanation.summary ||
                    'Candidate evaluation completed.'}
                </p>
              </div>

              <div className="hero-status">
                <span className="evaluation-status">
                  {candidate.score_status || 'Not evaluated'}
                </span>

                <span>
                  Rank #{candidate.rank ?? '—'}
                </span>

                <span>
                  {candidate.evidence_coverage ?? 0}% evidence coverage
                </span>
              </div>
            </section>

            {/* SCORE INFORMATION */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Score Overview</h3>
                <p>Actual results from the evaluation engine</p>
              </div>

              <div className="evaluation-stats">
                <div>
                  <span>Final Score</span>
                  <strong>{formatScore(getScore(candidate))}</strong>
                </div>

                <div>
                  <span>Provisional Score</span>
                  <strong>{formatScore(
                    typeof candidate.provisional_score === 'number'
                      ? candidate.provisional_score
                      : null
                  )}</strong>
                </div>

                <div>
                  <span>Evidence Coverage</span>
                  <strong>{candidate.evidence_coverage ?? 0}%</strong>
                </div>

                <div>
                  <span>Evaluated Weight</span>
                  <strong>{explanation.evaluated_weight ?? '—'}%</strong>
                </div>

                <div>
                  <span>Unevaluated Weight</span>
                  <strong>{explanation.unevaluated_weight ?? '—'}%</strong>
                </div>

                <div>
                  <span>Matched Required Skills</span>
                  <strong>
                    {candidate.matched_count ?? explanation.satisfied?.length ?? 0}
                  </strong>
                </div>
              </div>
            </section>

            {/* SCORE BREAKDOWN */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Scoring Breakdown</h3>
                <p>
                  Component scores and weights used by the existing scoring engine.
                </p>
              </div>

              <div className="component-grid">
                {renderComponent('Required Skills', 'required_skills')}
                {renderComponent('Semantic Relevance', 'semantic_relevance')}
                {renderComponent('Experience', 'experience')}
                {renderComponent('Education', 'education')}
                {renderComponent('Preferred Skills', 'preferred_skills')}
              </div>

              <div className="scoring-explanations">
                <h4>Scoring Explanations</h4>

                {(explanation.scoring_explanations || []).map(
                  (item: string, index: number) => (
                    <div key={index}>
                      <CheckCircle2 size={15} />
                      <span>{item}</span>
                    </div>
                  )
                )}
              </div>
            </section>

            {/* REQUIRED SKILL ANALYSIS */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Required Skill Evaluation</h3>
                <p>
                  Individual assessment of each required skill.
                </p>
              </div>

              {renderSkillAnalysis(
                requiredSkills,
                'No required skill analysis available.'
              )}
            </section>

            {/* PREFERRED SKILL ANALYSIS */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Preferred Skill Evaluation</h3>
                <p>
                  Assessment of additional preferred skills.
                </p>
              </div>

              {renderSkillAnalysis(
                preferredSkills,
                'No preferred skill analysis available.'
              )}
            </section>

            {/* SKILL SUMMARY */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Skill Summary</h3>
              </div>

              <div className="skill-summary-grid">
                <div>
                  <h4>Matched / Evidenced</h4>
                  <SkillList
                    skills={explanation.satisfied || []}
                    emptyText="No matched skills."
                  />
                </div>

                <div>
                  <h4>Related Skills</h4>
                  <SkillList
                    skills={explanation.related_skills || []}
                    emptyText="No related skills reported."
                  />
                </div>

                <div>
                  <h4>Missing Skills</h4>
                  <SkillList
                    skills={explanation.missing_skills || []}
                    emptyText="No missing skills reported."
                  />
                </div>

                <div>
                  <h4>Unverified Skills</h4>
                  <SkillList
                    skills={explanation.not_verified || []}
                    emptyText="No unverified skills reported."
                  />
                </div>
              </div>
            </section>

            {/* EXPERIENCE */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Experience Evaluation</h3>
                <p>Experience extracted from the resume.</p>
              </div>

              <div className="evaluation-stats">
                <div>
                  <span>Total Experience</span>
                  <strong>
                    {profile.total_experience_years ?? 0} years
                  </strong>
                </div>

                <div>
                  <span>Professional Experience</span>
                  <strong>
                    {profile.professional_experience_years ?? 'Not stated'}
                  </strong>
                </div>

                <div>
                  <span>Internship Experience</span>
                  <strong>
                    {profile.internship_experience_years ?? 0} years
                  </strong>
                </div>

                <div>
                  <span>Relevant Experience</span>
                  <strong>
                    {profile.relevant_experience_years ?? 'Not available'}
                  </strong>
                </div>
              </div>

              {explanation.experience_analysis && (
                <div className="analysis-note">
                  <strong>Evaluation result</strong>
                  <p>
                    {explanation.experience_analysis.explanation ||
                      explanation.experience_analysis.status}
                  </p>
                </div>
              )}

              {internships.length > 0 && (
                <>
                  <h4 className="subsection-title">Internship Evidence</h4>
                  <div className="evidence-list">
                    {internships.map((item: string, index: number) => (
                      <div key={index}>
                        <CheckCircle2 size={15} />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>

            {/* EDUCATION */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Education Evaluation</h3>
              </div>

              {education.length > 0 ? (
                <div className="evidence-list">
                  {education.map((item: string, index: number) => (
                    <div key={index}>
                      <FileText size={15} />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No education details extracted.</p>
              )}

              {explanation.education_analysis && (
                <div className="analysis-note">
                  <strong>Education assessment</strong>
                  <p>
                    {explanation.education_analysis.explanation ||
                      explanation.education_analysis.status}
                  </p>
                </div>
              )}

              {profile.education_details?.length > 0 && (
                <div className="evidence-list">
                  {profile.education_details.map(
                    (item: any, index: number) => (
                      <div key={index}>
                        <FileText size={15} />
                        <span>
                          {typeof item === 'object'
                            ? Object.entries(item)
                                .map(([key, value]) =>
                                  `${key.replaceAll('_', ' ')}: ${formatValue(value)}`
                                )
                                .join(' · ')
                            : item}
                        </span>
                      </div>
                    )
                  )}
                </div>
              )}
            </section>

            {/* PROJECT EVIDENCE */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Project Evidence</h3>
                <p>
                  Projects extracted from the candidate's resume.
                </p>
              </div>

              <div className="evidence-list">
                {projects.length > 0 ? (
                  projects.map((item: string, index: number) => (
                    <div key={index}>
                      <FileText size={15} />
                      <span>{item}</span>
                    </div>
                  ))
                ) : (
                  <p className="muted">
                    No project evidence available.
                  </p>
                )}
              </div>
            </section>

            {/* CERTIFICATIONS */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Certifications</h3>
              </div>

              <SkillList
                skills={certifications}
                emptyText="No certifications extracted."
              />
            </section>

            {/* RANKING INFORMATION */}

            <section className="evaluation-section">
              <div className="section-title">
                <h3>Ranking Information</h3>
              </div>

              <div className="analysis-note">
                <p>
                  <strong>Ranking basis:</strong>{' '}
                  {candidate.ranking_basis || 'Not available'}
                </p>

                <p>
                  <strong>Ranking status:</strong>{' '}
                  {candidate.ranking_status || 'Not available'}
                </p>

                {candidate.ranking_warning && (
                  <p>
                    <strong>Warning:</strong>{' '}
                    {candidate.ranking_warning}
                  </p>
                )}
              </div>
            </section>

            <div className="report-footer">
              Evaluation method: {explanation.scoring_method || 'Not specified'}
            </div>
          </>
        )
      })()}
    </div>
  </div>
)}

      {/* COMPARISON / RANKING MODAL */}

      {modalData && (

        <div
          className="modal-overlay"
          onClick={closeModals}
        >

          <div
            className="modal"
            onClick={event => event.stopPropagation()}
          >

            <div className="modal-header">

              <h2>{modalTitle}</h2>

              <button
                className="close-button"
                onClick={closeModals}
              >
                <X size={20} />
              </button>

            </div>

            {modalTitle === 'Candidate Comparison' ? (
  <ComparisonView
    data={modalData}
  />
) : modalTitle === 'Ranking Explanation' ? (
  <RankingExplanationView
    data={modalData}
  />
) : (
  <pre>{JSON.stringify(modalData, null, 2)}</pre>
)}

          </div>

        </div>

      )}

    </div>
  )
}

// --------------------------------
// STAT CARD COMPONENT
// --------------------------------

function StatCard({
  icon,
  title,
  value,
  subtitle,
}: {
  icon: ReactNode
  title: string
  value: string
  subtitle: string
}) {

  return (

    <div className="stat-card">

      <div className="stat-icon">
        {icon}
      </div>

      <p>{title}</p>

      <h2>{value}</h2>

      <span>{subtitle}</span>

    </div>

  )
}

// --------------------------------
// SKILL LIST COMPONENT
// --------------------------------

function SkillList({
  skills,
  emptyText,
}: {
  skills: string[]
  emptyText: string
}) {

  if (!skills.length) {
    return <p className="muted">{emptyText}</p>
  }

  return (

    <div className="skill-list">

      {skills.map((skill, index) => (
        <span
          className="skill-tag"
          key={`${skill}-${index}`}
        >
          {skill}
        </span>
      ))}

    </div>

  )
}

function ComparisonView({ data }: { data: any }) {
  const comparisonCandidates = Array.isArray(data?.candidates)
    ? data.candidates
    : []

  if (!comparisonCandidates.length) {
    return (
      <div className="empty">
        No candidate comparison data available.
      </div>
    )
  }

  const allSkills: string[] = Array.from(
  new Set<string>(
    comparisonCandidates.flatMap((candidate: any): string[] =>
      Array.isArray(candidate.skills)
        ? candidate.skills
            .filter((skill: unknown): skill is string =>
              typeof skill === 'string'
            )
            .map((skill: string) => skill.toLowerCase())
        : []
    )
  )
).sort()

  const hasSkill = (candidate: any, skill: string) =>
    (candidate.skills || []).some(
      (item: string) =>
        item.toLowerCase() === skill
    )

  return (
    <div className="comparison-view">

      <div className="comparison-summary">
        <div>
          <span>Candidates Compared</span>
          <h2>{data.candidate_count ?? comparisonCandidates.length}</h2>
        </div>

        <div>
          <span>Comparison Type</span>
          <h2>Side-by-side</h2>
        </div>
      </div>

      <div className="comparison-cards">

        {comparisonCandidates.map((candidate: any, index: number) => (
          <div
            className="comparison-card"
            key={candidate.candidate_id ?? index}
          >

            <div className="comparison-card-header">
              <div className="candidate-avatar">
                {(candidate.name || 'C').charAt(0).toUpperCase()}
              </div>

              <div>
                <h3>{candidate.name || `Candidate ${index + 1}`}</h3>
                <span>
                  Candidate #{candidate.candidate_id ?? '—'}
                </span>
              </div>
            </div>

            <div className="comparison-score">
              <span>Match Score</span>
              <strong>
                {typeof candidate.score === 'number'
                  ? `${candidate.score.toFixed(1)}%`
                  : '—'}
              </strong>
            </div>

            <div className="comparison-details">

              <div>
                <span>Rank</span>
                <strong>
                  {candidate.rank != null
                    ? `#${candidate.rank}`
                    : 'Not ranked'}
                </strong>
              </div>

              <div>
                <span>Evaluation</span>
                <strong>
                  {candidate.score_status || '—'}
                </strong>
              </div>

              <div>
                <span>Evidence Coverage</span>
                <strong>
                  {candidate.evidence_coverage != null
                    ? `${candidate.evidence_coverage}%`
                    : '—'}
                </strong>
              </div>

              <div>
                <span>Total Experience</span>
                <strong>
                  {candidate.experience_years != null
                    ? `${candidate.experience_years} years`
                    : '—'}
                </strong>
              </div>

              <div>
                <span>Professional Experience</span>
                <strong>
                  {candidate.professional_experience_years != null
                    ? `${candidate.professional_experience_years} years`
                    : '—'}
                </strong>
              </div>

              <div>
                <span>Internship Experience</span>
                <strong>
                  {candidate.internship_experience_years != null
                    ? `${candidate.internship_experience_years} years`
                    : '—'}
                </strong>
              </div>

            </div>

            <div className="comparison-skills">
              <h4>Extracted Skills</h4>

              <div className="skill-list">
                {(candidate.skills || []).map(
                  (skill: string, skillIndex: number) => (
                    <span
                      className="skill-tag"
                      key={`${skill}-${skillIndex}`}
                    >
                      {skill}
                    </span>
                  )
                )}

                {!candidate.skills?.length && (
                  <span className="muted">
                    No skills available
                  </span>
                )}
              </div>
            </div>

          </div>
        ))}

      </div>

      <div className="skill-matrix">

        <h3>Skill Comparison Matrix</h3>

        <p>
          Skills extracted from each candidate's resume.
        </p>

        <div className="table-wrap">

          <table>

            <thead>
              <tr>
                <th>SKILL</th>

                {comparisonCandidates.map(
                  (candidate: any, index: number) => (
                    <th key={candidate.candidate_id ?? index}>
                      {candidate.name || `Candidate ${index + 1}`}
                    </th>
                  )
                )}

              </tr>
            </thead>

            <tbody>

              {allSkills.map(skill => (
                <tr key={skill}>

                  <td className="matrix-skill">
                    {skill}
                  </td>

                  {comparisonCandidates.map(
                    (candidate: any, index: number) => (
                      <td key={candidate.candidate_id ?? index}>
                        {hasSkill(candidate, skill) ? (
                          <span className="skill-present">
                            ✓ Present
                          </span>
                        ) : (
                          <span className="skill-absent">
                            — Not listed
                          </span>
                        )}
                      </td>
                    )
                  )}

                </tr>
              ))}

              {!allSkills.length && (
                <tr>
                  <td
                    colSpan={comparisonCandidates.length + 1}
                    className="empty"
                  >
                    No extracted skills available.
                  </td>
                </tr>
              )}

            </tbody>

          </table>

        </div>

      </div>

      <p className="comparison-disclaimer">
        Comparison is based on extracted resume information and
        existing evaluation results. It is intended to support
        recruiter decisions, not replace them.
      </p>

    </div>
  )
}

export default App