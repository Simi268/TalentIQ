// ======================================================
// TALENTIQ — AI RECRUITMENT INTELLIGENCE
// Complete Frontend Application
// ======================================================


// ======================================================
// 1. GLOBAL STATE
// ======================================================

let candidates = [];
let requirements = {};

let filesFailures = 0;
let currentJobId = null;
let isUploading = false;

const $ = id => document.getElementById(id);


// ======================================================
// 2. UTILITY FUNCTIONS
// ======================================================

const esc = value =>
    String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));


function toast(message) {
    const element = $('toast');

    if (!element) return;

    element.textContent = message;
    element.style.display = 'block';

    clearTimeout(toast.timer);

    toast.timer = setTimeout(() => {
        element.style.display = 'none';
    }, 3500);
}


function formatNumber(value, decimals = 2) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number.toFixed(decimals)
        : '—';
}

function formatExperience(value) {
    if (value === null || value === undefined || value === '') {
        return 'Not established';
    }

    const number = Number(value);

    return Number.isFinite(number)
        ? `${number.toFixed(2)} years`
        : 'Not established';
}

function experienceStatus(profile) {
    const professional = profile.professional_experience_years;
    const internship = profile.internship_experience_years;
    const stated = profile.stated_experience_years;

    if (professional != null || internship != null) {
        return 'Date-range evidence extracted';
    }

    if (stated != null) {
        return 'Claim only — dates not found';
    }

    return 'No dated experience detected';
}


// ======================================================
// EVIDENCE-AWARE SCORING HELPERS
// ======================================================

function candidateScore(candidate) {
    const value = candidate?.provisional_score ?? candidate?.score ??
        candidate?.explanation?.provisional_score ?? null;
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : null;
}

function getEvaluationStatus(candidate) {
    const explanation = candidate?.explanation || {};
    const value = candidate?.score_status ?? explanation.score_status ??
        candidate?.scoring?.score_status ?? 'unknown';
    return ['complete', 'partial', 'insufficient_evidence'].includes(value)
        ? value : 'unknown';
}

function getEvidenceCoverage(candidate) {
    const explanation = candidate?.explanation || {};
    const raw = candidate?.evidence_coverage ?? explanation.evidence_coverage ??
        candidate?.scoring?.evidence_coverage ?? null;
    if (raw === null || raw === undefined || raw === '') return null;
    const number = Number(raw);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : null;
}


// Required-skill evidence is deliberately separate from scoring completeness.
// Only exact matches count as covered; related, unverified and missing skills
// remain visible as separate categories rather than being silently blended.
function getRequiredSkillStats(candidate) {
    const explanation = candidate?.explanation || {};
    const analysis = explanation.required_skill_analysis || [];
    const requiredFromJD = requirements?.required_skills || [];

    let total = 0;
    let exact = 0;
    let related = 0;
    let unverified = 0;
    let missing = 0;

    if (Array.isArray(analysis) && analysis.length) {
        const seen = new Set();
        analysis.forEach(item => {
            const name = String(item.requirement || item.skill || '').trim().toLowerCase();
            if (!name || seen.has(name)) return;
            seen.add(name);
            total += 1;
            const status = String(item.status || '').toLowerCase();
            if (status === 'exact_match') exact += 1;
            else if (status === 'related_match') related += 1;
            else if (status === 'unverified' || status === 'needs_verification') unverified += 1;
            else if (status === 'missing') missing += 1;
            else unverified += 1;
        });
    } else {
        const matched = explanation.satisfied || [];
        const relatedSkills = explanation.related_skills || [];
        const unverifiedSkills = explanation.not_verified || [];
        const missingSkills = explanation.missing_skills || [];
        const allNames = [
            ...requiredFromJD,
            ...matched,
            ...relatedSkills,
            ...unverifiedSkills,
            ...missingSkills
        ].map(value => String(value).trim()).filter(Boolean);
        const unique = [...new Set(allNames.map(value => value.toLowerCase()))];
        total = unique.length;
        const has = (list, name) => list.some(value => String(value).trim().toLowerCase() === name);
        unique.forEach(name => {
            if (has(matched, name)) exact += 1;
            else if (has(relatedSkills, name)) related += 1;
            else if (has(missingSkills, name)) missing += 1;
            else unverified += 1;
        });
    }

    const coverage = total > 0 ? (exact / total) * 100 : null;
    return { total, exact, related, unverified, missing, coverage };
}

function requiredSkillCoverageHTML(candidate) {
    const stats = getRequiredSkillStats(candidate);
    if (stats.coverage === null) {
        return '<div class="coverage-unavailable">Required-skill analysis unavailable</div>';
    }
    return `
        <div class="skill-evidence-coverage" title="Exact matches / total required skills">
            <div class="coverage-heading">
                <span>Exact skill coverage</span>
                <strong>${stats.exact}/${stats.total} · ${stats.coverage.toFixed(1)}%</strong>
            </div>
            <div class="coverage-track skill-coverage-track">
                <span style="width:${stats.coverage}%"></span>
            </div>
            <div class="skill-evidence-counts">
                <span>${stats.related} related</span>
                <span>${stats.unverified} unverified</span>
                <span>${stats.missing} missing</span>
            </div>
        </div>`;
}

function getUnevaluatedWeight(candidate) {
    const explanation = candidate?.explanation || {};
    const raw = candidate?.unevaluated_weight ?? explanation.unevaluated_weight ?? null;
    if (raw === null || raw === undefined || raw === '') return null;
    const number = Number(raw);
    return Number.isFinite(number) ? Math.max(0, number) : null;
}

function evaluationBadge(status) {
    const labels = {
        complete: 'Complete',
        partial: 'Partial',
        insufficient_evidence: 'Insufficient evidence',
        unknown: 'Status unavailable'
    };
    return `<span class="evaluation-badge ${status}"><i></i>${labels[status] || labels.unknown}</span>`;
}

function evidenceCoverageHTML(candidate) {
    const coverage = getEvidenceCoverage(candidate);
    if (coverage === null) {
        return '<div class="coverage-unavailable">Coverage not supplied by API</div>';
    }
    return `
        <div class="evidence-coverage" title="${coverage.toFixed(1)}% of applicable scoring weight evaluated">
            <div class="coverage-heading"><span>Scoring completeness</span><strong>${coverage.toFixed(1)}%</strong></div>
            <div class="coverage-track"><span style="width:${coverage}%"></span></div>
        </div>`;
}

function componentBreakdown(candidate) {
    const explanation = candidate?.explanation || {};
    return explanation.score_breakdown || explanation.breakdown ||
        candidate?.score_breakdown || candidate?.breakdown || {};
}


// Interview prompts are deterministic suggestions based on extracted
// requirements/evidence. They are not generated by an LLM.
function buildInterviewQuestions(candidate, explanation) {
    const missing = explanation.missing_skills || [];
    const unverified = explanation.not_verified || [];
    const related = explanation.related_skills || [];
    const verify = explanation.verify_in_interview || [];

    const targets = [...new Set([
        ...unverified,
        ...verify,
        ...related,
        ...missing
    ])];

    const questions = [];

    targets.slice(0, 5).forEach(skill => {
        questions.push({
            focus: skill,
            question: `Describe a project or practical task where you used ${skill}. What was your specific contribution?`,
            signal: 'Ask for concrete steps, tools, decisions and outcomes.'
        });
    });

    // Keep actual project titles; reject repository/demo link labels.
    const excludedLabels = new Set([
        'github',
        'live demo',
        'github | live demo',
        'demo',
        'source code',
        'repository'
    ]);

    const projects = (candidate.profile?.projects || [])
        .map(project => {
            const title = typeof project === 'string'
                ? project
                : (project.title || project.name || '');

            return title.trim();
        })
        .filter(title =>
            title &&
            !excludedLabels.has(title.toLowerCase()) &&
            !/^https?:\/\//i.test(title)
        );

    projects.slice(0, 2).forEach(project => {
        questions.push({
            focus: 'Project validation',
            question: `Walk me through ${project}. What problem did it solve, how was it implemented, and what would you improve?`,
            signal: 'Validate ownership, technical depth and measurable outcomes.'
        });
    });

    if (!questions.length) {
        questions.push({
            focus: 'Technical depth',
            question: 'Choose the most relevant technical project on your resume and explain its architecture, trade-offs and a difficult problem you solved.',
            signal: 'Use follow-up questions to validate the candidate’s individual contribution.'
        });
    }

    return questions.slice(0, 7);
}
function renderJDInsights() {
    const target = $('jd-insight-grid');
    if (!target) return;

    const req = requirements || {};
    const required = req.required_skills || [];
    const preferred = req.preferred_skills || [];
    const responsibilities = req.responsibilities || req.key_responsibilities || [];
    const certifications = req.certifications || req.certification_requirements || [];
    const education = req.education || req.education_requirements || 'Not specified';
    const minExp = req.minimum_experience ?? req.min_experience_years;

    const items = [
        ['Required skills', required.length ? `${required.length} identified` : 'Not identified'],
        ['Preferred skills', preferred.length ? `${preferred.length} identified` : 'Not identified'],
        ['Minimum experience', minExp == null ? 'Not specified' : `${minExp} years`],
        ['Education', Array.isArray(education) ? education.join(', ') : education],
        ['Responsibilities', Array.isArray(responsibilities) ? `${responsibilities.length} identified` : (responsibilities ? 'Identified' : 'Not identified')],
        ['Certifications', Array.isArray(certifications) ? (certifications.length ? `${certifications.length} identified` : 'None specified') : (certifications || 'Not specified')]
    ];

    target.innerHTML = items.map(([label, value]) => `
        <div class="jd-insight-card">
            <span>${esc(label)}</span>
            <strong>${esc(value)}</strong>
        </div>
    `).join('');

    const hasAny = required.length || preferred.length || minExp != null ||
        responsibilities.length || certifications.length || education !== 'Not specified';
    if (!hasAny) {
        target.innerHTML = '<span class="muted">The parser did not return structured details for these fields. Review the original job description and edit the skill lists below.</span>';
    }
}

function renderRecruiterAnalytics() {
    const signalTarget = $('hiring-signals');
    const skillTarget = $('required-skill-analytics');

    if (!signalTarget || !skillTarget) return;

    if (!candidates.length) {
        signalTarget.innerHTML =
            '<span class="muted">Upload resumes to generate hiring signals.</span>';

        skillTarget.innerHTML =
            '<span class="muted">Create a job description to see skill coverage.</span>';

        return;
    }

    // ----------------------------------------
    // HIRING SIGNALS
    // ----------------------------------------

    const bands = [
        ['Strong match', c => candidateScore(c) !== null && candidateScore(c) >= 75],
        ['Potential match', c => candidateScore(c) !== null && candidateScore(c) >= 50 && candidateScore(c) < 75],
        ['Lower match signal', c => candidateScore(c) !== null && candidateScore(c) < 50],
        ['Complete evaluation', c => getEvaluationStatus(c) === 'complete'],
        ['Needs evidence review', c => getEvaluationStatus(c) !== 'complete']
    ];

    signalTarget.innerHTML = bands.map(([label, predicate]) => {
        const count = candidates.filter(predicate).length;
        const pct = count / candidates.length * 100;

        return `
            <div class="analytics-row">
                <div class="analytics-row-label">
                    <span>${esc(label)}</span>
                    <strong>${count}/${candidates.length}</strong>
                </div>
                <div class="analytics-track">
                    <span style="width:${pct}%"></span>
                </div>
            </div>
        `;
    }).join('');

    // ----------------------------------------
    // REQUIRED SKILL EVIDENCE ANALYTICS
    // ----------------------------------------

    const required = requirements.required_skills || [];

    if (!required.length) {
        skillTarget.innerHTML =
            '<span class="muted">No required skills have been extracted. Review the job description requirements.</span>';

        return;
    }

    skillTarget.innerHTML = required.map(skill => {
        const key = String(skill).trim().toLowerCase();

        const counts = {
            exact: 0,
            related: 0,
            unverified: 0,
            missing: 0
        };

        candidates.forEach(candidate => {
            const analysis =
                candidate.explanation?.required_skill_analysis || [];

            const item = analysis.find(entry =>
                String(entry.requirement || entry.skill || '')
                    .trim()
                    .toLowerCase() === key
            );

            if (item) {
                const status = String(item.status || '').toLowerCase();

                if (status === 'exact_match') {
                    counts.exact++;
                } else if (status === 'related_match') {
                    counts.related++;
                } else if (
                    status === 'unverified' ||
                    status === 'needs_verification'
                ) {
                    counts.unverified++;
                } else {
                    counts.missing++;
                }

                return;
            }

            // Legacy response fallback
            const explanation = candidate.explanation || {};

            const has = list =>
                (list || []).some(value =>
                    String(value).trim().toLowerCase() === key
                );

            if (has(explanation.satisfied)) {
                counts.exact++;
            } else if (has(explanation.related_skills)) {
                counts.related++;
            } else if (has(explanation.not_verified)) {
                counts.unverified++;
            } else {
                counts.missing++;
            }
        });

        const total = candidates.length;
        const row = (label, count, status) => {
    const pct = total ? (count / total) * 100 : 0;

    return `
        <div class="analytics-row">
            <div class="analytics-row-label">
                <span>${esc(label)}</span>
                <strong>${count}/${total}</strong>
            </div>

            <div class="analytics-track ${status}">
                <span style="width: ${pct}%"></span>
            </div>
        </div>
    `;
};

        

        return `
            <div class="required-skill-card" style="margin-bottom:18px;">

                <h4 style="margin-bottom:10px;">
                    ${esc(skill)}
                </h4>

                ${row('Exact matches', counts.exact, 'exact')}
${row('Related matches', counts.related, 'related')}
${row('Unverified', counts.unverified, 'unverified')}
${row('Missing', counts.missing, 'missing')}

            </div>
        `;
    }).join('');
}


function formatList(items) {
    if (!Array.isArray(items) || !items.length) {
        return 'Not available';
    }

    return items.map(esc).join(', ');
}


function showModal(html) {
    $('dialog').innerHTML = html;
    $('modal').style.display = 'flex';
}


function closeModal() {
    $('modal').style.display = 'none';
}


// ======================================================
// 3. API HELPER
// ======================================================

async function api(url, options = {}) {

    const response = await fetch(url, options);

    let data;

    try {
        data = await response.json();
    } catch (_) {
        data = {
            detail: 'The server returned an invalid response.'
        };
    }

    if (!response.ok) {

        const message =
            typeof data.detail === 'string'
                ? data.detail
                : JSON.stringify(data.detail || 'Request failed');

        throw new Error(message);
    }

    return data;
}


// ======================================================
// 4. APPLICATION INITIALIZATION
// ======================================================

async function init() {

    const jobs = await api('/api/jobs');

    $('jobpick').innerHTML = `
        <option value="">Select a role</option>

        ${jobs.map(job => `
            <option value="${job.id}">
                ${esc(job.title)}
            </option>
        `).join('')}
    `;

    // Start with no job selected.
    // Existing jobs remain available in the dropdown.
    currentJobId = null;
    candidates = [];
    requirements = {};

    clearJobForm();
    render();
}


// ======================================================
// 5. JOB DESCRIPTION INTELLIGENCE
// ======================================================

function showReq(data) {

    requirements = data || {};

    const required = requirements.required_skills || [];
    const preferred = requirements.preferred_skills || [];

    $('reqs').innerHTML = `

        ${required.map(skill => `
            <span class="pill green">
                Must · ${esc(skill)}
            </span>
        `).join('')}

        ${preferred.map(skill => `
            <span class="pill">
                Preferred · ${esc(skill)}
            </span>
        `).join('')}

        ${requirements.minimum_experience
            ? `<span class="pill">
                ${esc(requirements.minimum_experience)}+ years
               </span>`
            : ''
        }

    ` || '<span class="muted">No requirements extracted.</span>';

    $('reqedit').style.display = 'block';

    $('reqrequired').value = required.join(', ');

    $('reqpreferred').value = preferred.join(', ');

    renderJDInsights();

}

function clearJobForm() {

    currentJobId = null;
    requirements = {};
    candidates = [];

    $('jobtitle').value = '';
    $('jobdesc').value = '';

    $('reqs').innerHTML =
        '<span class="muted">Select a role or analyze a new job description.</span>';

    $('reqrequired').value = '';
    $('reqpreferred').value = '';

    $('reqedit').style.display = 'none';

    $('jd-insight-grid').innerHTML =
        '<span class="muted">Select a role or analyze a job description to inspect its requirements.</span>';

    render();
}

// ======================================================
// 6. CREATE JOB
// ======================================================

async function createJob() {

    const description = $('jobdesc').value.trim();
    const title = $('jobtitle').value.trim();

    try {

        if (!description) {
            throw new Error('Enter a job description first.');
        }

        const job = await api('/api/jobs', {

            method: 'POST',

            headers: {
                'Content-Type': 'application/json'
            },

            body: JSON.stringify({
                title: title || null,
                description
            })

        });

        // Refresh available jobs
        await refreshJobs();

        // Select the newly created job
        $('jobpick').value = job.id;
        currentJobId = job.id;

        // Display extracted requirements
        showReq(job.requirements);

        // Load candidate results once
        await loadResults();

        // Preserve the original JD and title
        $('jobdesc').value = description;
        $('jobtitle').value = title;

        // Stay on the Job Descriptions page
        switchPage('jobs');

        toast('Job description analyzed successfully.');

    } catch (error) {

        toast(error.message);

    }

}


// ======================================================
// 7. REFRESH JOB LIST
// ======================================================

async function refreshJobs() {

    const jobs = await api('/api/jobs');

    const previousJob = $('jobpick').value;

    $('jobpick').innerHTML = `
        <option value="">Select a role</option>

        ${jobs.map(job => `
            <option value="${job.id}">
                ${esc(job.title)}
            </option>
        `).join('')}
    `;

    const exists = jobs.some(
        job => String(job.id) === String(previousJob)
    );

    if (exists) {
        $('jobpick').value = previousJob;
    } else if (jobs.length) {
        $('jobpick').value = jobs[0].id;
    }

    currentJobId = $('jobpick').value || null;

}


// ======================================================
// 8. SAVE REVIEWED REQUIREMENTS
// ======================================================

async function saveRequirements() {

    try {

        const id = $('jobpick').value;

        if (!id) {
            throw new Error('Select a job first.');
        }

        const splitSkills = elementId => {

            return $(elementId).value
                .split(',')
                .map(skill => skill.trim())
                .filter(Boolean);

        };

        const result = await api(
            `/api/jobs/${id}/requirements`,
            {

                method: 'PATCH',

                headers: {
                    'Content-Type': 'application/json'
                },

                body: JSON.stringify({

                    required_skills:
                        splitSkills('reqrequired'),

                    preferred_skills:
                        splitSkills('reqpreferred')

                })

            }
        );

        showReq(result.requirements);

        await loadResults();

        toast('Requirements saved and candidates rescored.');

    } catch (error) {

        toast(error.message);

    }

}


// ======================================================
// 9. SELECT JOB
// ======================================================

async function selectJob() {

    const id = $('jobpick').value;

    // Nothing selected: clear all previous job information.
    if (!id) {
        clearJobForm();
        return;
    }

    try {

        const job = await api(`/api/jobs/${id}`);

        currentJobId = id;

        // Load original job information.
        $('jobtitle').value = job.title || '';
        $('jobdesc').value =
            job.description || job.job_description || '';

        // Load extracted requirements.
        showReq(job.requirements);

        // Load candidates belonging to this job.
        await loadResults();

    } catch (error) {

        clearJobForm();
        toast(error.message);

    }
}


// ======================================================
// 10. LOAD CANDIDATE RESULTS
// ======================================================

async function loadResults() {

    const id = $('jobpick').value;

    if (!id) {

        candidates = [];

        render();

        return;

    }

    currentJobId = id;

    candidates = await api(
        `/api/matching/results/${id}`
    );

    if (!Array.isArray(candidates)) {
        candidates = [];
    }

    render();

}


// ======================================================
// 11. DASHBOARD RENDERING
// ======================================================

function render() {
    const total = candidates.length;
    const scored = candidates.map(candidateScore).filter(value => value !== null);
    const average = scored.length
        ? scored.reduce((sum, value) => sum + value, 0) / scored.length
        : null;

    $('mcount').textContent = total;
    $('mavg').textContent = average === null ? '—' : average.toFixed(1) + '%';
    $('mstrong').textContent = candidates.filter(candidate => {
        const score = candidateScore(candidate);
        return score !== null && score >= 75;
    }).length;
    $('mfail').textContent = filesFailures;

    const completeCount = candidates.filter(c => getEvaluationStatus(c) === 'complete').length;
    const partialCount = candidates.filter(c => getEvaluationStatus(c) === 'partial').length;
    const coverageValues = candidates.map(getEvidenceCoverage).filter(v => v !== null);
    const avgCoverage = coverageValues.length
        ? coverageValues.reduce((a, b) => a + b, 0) / coverageValues.length
        : null;

    if ($('mevaluated')) $('mevaluated').textContent = `${completeCount}/${total}`;
    if ($('mcoverage')) $('mcoverage').textContent = avgCoverage === null ? '—' : `${avgCoverage.toFixed(1)}%`;
    if ($('mavg-note')) $('mavg-note').textContent = `${scored.length} scored candidate(s); ${partialCount} partial evaluation(s)`;

    const skillCoverageValues = candidates
        .map(getRequiredSkillStats)
        .map(stats => stats.coverage)
        .filter(value => value !== null);
    const averageSkillCoverage = skillCoverageValues.length
        ? skillCoverageValues.reduce((sum, value) => sum + value, 0) / skillCoverageValues.length
        : null;
    if ($('mskillcoverage')) {
        $('mskillcoverage').textContent = averageSkillCoverage === null
            ? '—'
            : `${averageSkillCoverage.toFixed(1)}%`;
    }

    $('tbody').innerHTML = total ? candidates.map((candidate, index) => {
        const score = candidateScore(candidate);
        const status = getEvaluationStatus(candidate);
        const matched = candidate.explanation?.satisfied || [];
        const unverified = candidate.explanation?.not_verified || [];
        const missing = candidate.explanation?.missing_skills || [];
        const profile = candidate.profile || {};
        const unresolved = [...new Set([...missing, ...unverified])];

        return `
            <tr>
                <td>
    <span class="rank-chip">
        #${esc(
            candidateScore(candidate) === null
                ? '—'
                : (candidate.rank ?? index + 1)
        )}
    </span>
</td>
                <td>
                    <div class="candidate-cell">
                        <input type="checkbox" class="sel" value="${esc(candidate.id)}" aria-label="Select ${esc(candidate.name)}">
                        <div class="candidate-identity">
                            <button type="button" class="link name" onclick="profile(${Number(candidate.id)})">${esc(candidate.name || 'Unknown candidate')}</button>
                            <div class="sub">${esc(candidate.filename || 'Resume')}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="match-score-cell">
                        <strong class="score">${score === null ? 'Not scored' : score.toFixed(2) + '%'}</strong>
                        <div class="match-progress"><span style="width:${score === null ? 0 : score}%"></span></div>
                    </div>
                </td>
                <td>
                    ${evaluationBadge(status)}
                    ${evidenceCoverageHTML(candidate)}
                    ${requiredSkillCoverageHTML(candidate)}
                </td>
                <td>
    <div><strong>Professional:</strong> ${esc(formatExperience(profile.professional_experience_years))}</div>
    <div class="sub">Internship: ${esc(formatExperience(profile.internship_experience_years))}</div>
    <div class="sub">Stated: ${esc(formatExperience(profile.stated_experience_years))}</div>
</td>
                <td><span class="matched-count">${matched.length}</span> matched</td>
                <td><div class="skill-overflow">${unresolved.length ? unresolved.slice(0, 4).map(esc).join(', ') : '—'}</div></td>
                <td><button type="button" class="link delete-link" onclick="removeCandidate(${Number(candidate.id)})">Delete</button></td>
            </tr>`;
    }).join('') : `
        <tr><td colspan="8" class="empty-state">No candidates analyzed for this role yet. Create a job description and upload resumes to begin.</td></tr>`;

    renderSkillsCoverage();
    renderScoreDistribution();
    renderRecentActivity();
    renderRecruiterAnalytics();
}

// ======================================================
// 12. SKILLS COVERAGE
// ======================================================

function renderScoreDistribution() {
    const bins = [0, 0, 0, 0, 0];
    let unscored = 0;

    candidates.forEach(candidate => {
        const score = candidateScore(candidate);

        if (
            score === null ||
            score === undefined ||
            !Number.isFinite(Number(score))
        ) {
            unscored++;
            return;
        }

        const numericScore = Number(score);

        const index = Math.min(
            4,
            Math.max(0, Math.floor(numericScore / 20))
        );

        bins[index]++;
    });

    const scoredTotal = bins.reduce(
        (sum, count) => sum + count,
        0
    );

    $('distribution').innerHTML = bins.map(
        (count, index) => `
            <span style="height:${Math.max(4, count * 16)}px">
                <small>
                    ${index * 20}–${index * 20 + 19}% · ${count}
                </small>
            </span>
        `
    ).join('') + `
        <div class="muted" style="margin-top:12px;">
            Scored: ${scoredTotal} · Not scored: ${unscored}
        </div>
    `;
}

function renderSkillsCoverage() {
    const skillCounts = {};

    candidates.forEach(candidate => {
        const skills = candidate.explanation?.satisfied || [];

        skills.forEach(skill => {
            skillCounts[skill] = (skillCounts[skill] || 0) + 1;
        });
    });

    $('skills').innerHTML =
        Object.entries(skillCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 15)
            .map(([skill, count]) => `
                <span class="pill green">
                    ${esc(skill)} · ${count}
                </span>
            `).join('')
        || '<span class="muted">No supported skills available.</span>';
}
// ======================================================
// 13. MATCH SCORE DISTRIBUTION
// ======================================================

function renderScoreDistribution() {

    const bins = [0, 0, 0, 0, 0];

    candidates.forEach(candidate => {

        const score = candidateScore(candidate) ?? 0;

        const index = Math.min(
            4,
            Math.max(0, Math.floor(score / 20))
        );

        bins[index]++;

    });

    $('distribution').innerHTML = bins.map(
        (count, index) => `

            <span style="height:${Math.max(4, count * 16)}px">

                <small>
                    ${index * 20}–${index * 20 + 19}% · ${count}
                </small>

            </span>

        `
    ).join('');

}


// ======================================================
// 14. RECENT PROCESSING ACTIVITY
// ======================================================

function renderRecentActivity() {

    $('activity').innerHTML =

        candidates.slice(0, 5).map(candidate => `

            <div style="
                padding:9px 0;
                border-bottom:1px solid #eef1f5
            ">

                <b>
                    ${esc(candidate.filename)}
                </b>

                <span class="status" style="float:right">
                    Processed · ${candidateScore(candidate) === null ? 'Not scored' : candidateScore(candidate).toFixed(2) + '%'}
                </span>

            </div>

        `).join('')

        || 'No resumes processed yet.';

}


// ======================================================
// 15. RESUME UPLOAD WITH PROGRESS
// ======================================================

async function uploadFiles() {

    if (isUploading) {
        return toast('An upload is already in progress.');
    }

    const files = [...$('files').files];

    const jobId = $('jobpick').value;

    if (!jobId) {

        $('files').value = '';

        return toast('Create or select a job first.');

    }

    if (!files.length) return;


    // Basic frontend validation

    const allowedExtensions = ['pdf', 'docx', 'txt'];

    const invalidFiles = files.filter(file => {

        const extension =
            file.name.split('.').pop().toLowerCase();

        return !allowedExtensions.includes(extension)
            || file.size > 8 * 1024 * 1024;

    });

    if (invalidFiles.length) {

        toast(
            `${invalidFiles.length} file(s) have unsupported formats or exceed 8 MB.`
        );

        $('files').value = '';

        return;

    }


    isUploading = true;

    const uploadLabel =
        document.querySelector('.upload label');

    uploadLabel.style.pointerEvents = 'none';

    uploadLabel.style.opacity = '0.6';


    // Initial upload UI

    $('uploadstatus').textContent =
        `Preparing ${files.length} resume(s)...`;

    $('filelist').innerHTML = `

        <div class="upload-progress-container">

            <div class="progress-heading">

                <span>Uploading resumes</span>

                <strong id="progress-percent">
                    0%
                </strong>

            </div>

            <div class="progress-track">

                <div
                    class="progress-fill"
                    id="progress-fill"
                    style="width:0%"
                ></div>

            </div>

            <div
                id="progress-detail"
                class="muted"
            >
                Preparing files...
            </div>

        </div>

    `;


    const formData = new FormData();

    files.forEach(file => {
        formData.append('files', file);
    });


    const xhr = new XMLHttpRequest();

    xhr.open(
        'POST',
        `/api/resumes/upload?job_id=${encodeURIComponent(jobId)}`
    );


    // Upload progress

    xhr.upload.addEventListener('progress', event => {

        if (!event.lengthComputable) return;

        const percentage = Math.round(
            (event.loaded / event.total) * 100
        );

        $('progress-percent').textContent =
            `${percentage}%`;

        $('progress-fill').style.width =
            `${percentage}%`;

        $('progress-detail').textContent =
            `Transferring ${files.length} resume(s)...`;

        $('uploadstatus').textContent =
            `Uploading: ${percentage}%`;

    });


    // Upload completed

    xhr.onload = async () => {

        try {

            const result = JSON.parse(
                xhr.responseText || '{}'
            );

            if (xhr.status < 200 || xhr.status >= 300) {

                throw new Error(
                    result.detail || 'Resume upload failed.'
                );

            }

            const results = result.results || [];

            // IMPORTANT:
            // Count statuses from individual results.
            // Do not rely on result.processed alone.

            const processed = results.filter(item =>
                item.status === 'processed' ||
                item.status === 'success'
            ).length;

            const failed = results.filter(item =>
                item.status === 'failed'
            ).length;

            const duplicates = results.filter(item =>
                item.status === 'duplicate'
            ).length;

            filesFailures += failed;


            // Update progress

            $('progress-percent').textContent = '100%';

            $('progress-fill').style.width = '100%';

            $('progress-detail').textContent =
                'Server response received. Processing results are ready.';


            // Update summary

            $('uploadstatus').textContent =
                `${processed} processed · ${duplicates} duplicates · ${failed} failed`;


            $('filelist').innerHTML = `

                <div class="batch-summary">

                    <div class="batch-stat">

                        <strong>${files.length}</strong>

                        <span>Submitted</span>

                    </div>

                    <div class="batch-stat success">

                        <strong>${processed}</strong>

                        <span>Processed</span>

                    </div>

                    <div class="batch-stat error">

                        <strong>${failed}</strong>

                        <span>Failed</span>

                    </div>

                </div>


                <h4>File Processing Results</h4>


                <div class="file-results">

                    ${results.map(item => {

                        const success =
                            item.status === 'processed' ||
                            item.status === 'success';

                        const duplicate =
                            item.status === 'duplicate';

                        const statusClass = success
                            ? 'success'
                            : duplicate
                                ? ''
                                : 'error';

                        const icon = success
                            ? '✓'
                            : duplicate
                                ? '↻'
                                : '✕';

                        const statusText = success
                            ? 'Processed'
                            : duplicate
                                ? 'Duplicate'
                                : 'Failed';

                        const detail = success
                            ? 'Processed successfully'
                            : duplicate
                                ? 'This resume already exists for the selected role.'
                                : item.error || 'Processing failed';

                        return `

                            <div class="file-result">

                                <span class="file-result-icon ${statusClass}">
                                    ${icon}
                                </span>

                                <div class="file-result-info">

                                    <strong>
                                        ${esc(item.filename)}
                                    </strong>

                                    <small>
                                        ${esc(detail)}
                                    </small>

                                </div>

                                <span class="file-result-status ${statusClass}">
                                    ${statusText}
                                </span>

                            </div>

                        `;

                    }).join('')}

                </div>

            `;


            // Refresh candidate data

            await loadResults();

            toast(
                `${processed} resume(s) processed successfully.`
            );


        } catch (error) {

            $('uploadstatus').textContent =
                'Processing failed';

            $('progress-detail').textContent =
                error.message;

            toast(error.message);

        } finally {

            isUploading = false;

            uploadLabel.style.pointerEvents = '';

            uploadLabel.style.opacity = '';

            $('files').value = '';

        }

    };


    // Network failure

    xhr.onerror = () => {

        isUploading = false;

        uploadLabel.style.pointerEvents = '';

        uploadLabel.style.opacity = '';

        $('uploadstatus').textContent =
            'Network error';

        $('progress-detail').textContent =
            'Could not connect to the server.';

        $('files').value = '';

        toast('Network error during upload.');

    };


    xhr.onabort = () => {

        isUploading = false;

        uploadLabel.style.pointerEvents = '';

        uploadLabel.style.opacity = '';

        $('uploadstatus').textContent =
            'Upload cancelled';

        $('files').value = '';

        toast('Upload was cancelled.');

    };


    xhr.send(formData);

}


// ======================================================
// 16. CANDIDATE PROFILE INTELLIGENCE
// ======================================================

async function profile(id) {

    try {

        const candidate = await api(
            `/api/candidates/${id}`
        );

        const profile = candidate.profile || {};

        const explanation = candidate.explanation || {};


        const satisfied =
            explanation.satisfied || [];

        const unverified =
            explanation.not_verified || [];

        const verify =
            explanation.verify_in_interview || [];


        const scoreBreakdown = componentBreakdown(candidate);
        const evaluationStatus = getEvaluationStatus(candidate);
        const evidenceCoverage = getEvidenceCoverage(candidate);
        const unevaluatedWeight = getUnevaluatedWeight(candidate);
        const requiredSkillStats = getRequiredSkillStats(candidate);
        const requirementAnalysis =
    explanation.required_skill_analysis || [];

const requirementEvidenceHTML = requirementAnalysis.length
    ? requirementAnalysis.map(item => {
        const status = item.status || 'unverified';

        const labels = {
            exact_match: 'Exact match',
            related_match: 'Related match',
            needs_verification: 'Needs verification',
            unverified: 'Unverified',
            missing: 'Missing'
        };

        const evidence = item.supporting_evidence || [];

        return `
            <div class="panel" style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;gap:12px;">
                    <strong>${esc(item.requirement)}</strong>
                    <span class="pill">${esc(labels[status] || status)}</span>
                </div>

                <div class="sub" style="margin-top:8px;">
                    ${evidence.length
                        ? evidence.map(text => `<p>${esc(text)}</p>`).join('')
                        : 'No direct supporting quotation available.'}
                </div>

                ${item.explanation
                    ? `<p class="sub">${esc(item.explanation)}</p>`
                    : ''}
            </div>
        `;
    }).join('')
    : '<p class="muted">Requirement-level evidence unavailable.</p>';
        const profileScore = candidateScore(candidate);


        // EXPERIENCE EVIDENCE

        const experienceEvidence =
            profile.experience_evidence || [];

        const internshipEvidence =
            profile.internship_evidence || [];


        // SKILL SECTIONS

        const skillHTML = items => {

            if (!items.length) {
                return '<span class="muted">No evidence available.</span>';
            }

            return items.map(skill => `

                <span class="pill green">
                    ${esc(skill)}
                </span>

            `).join('');

        };


        // SCORE BREAKDOWN

        const breakdownHTML = Object.entries(scoreBreakdown).map(([key, raw]) => {
            const item = raw && typeof raw === 'object' ? raw : { score: raw };
            const componentScore = item.score ?? item.verified_score ?? null;
            const weight = item.weight;
            const status = item.status || (componentScore == null ? 'not_evaluated' : 'evaluated');
            return `
                <div class="component-row">
                    <div><strong>${esc(key.replaceAll('_', ' '))}</strong><small>${weight == null ? 'Weight unavailable' : `${formatNumber(weight, 1)}% weight`}</small></div>
                    <div class="component-result"><b>${componentScore == null ? '—' : `${formatNumber(componentScore, 1)}%`}</b><span>${esc(status.replaceAll('_', ' '))}</span></div>
                </div>`;
        }).join('');


        showModal(`

            <button
                class="close"
                onclick="closeModal()"
            >
                Close
            </button>


            <div class="eyebrow">
                Candidate Intelligence
            </div>


            <h2>
                ${esc(candidate.name)}
            </h2>


            <div class="muted">
                ${esc(candidate.filename)}
            </div>


            <div class="requirements">

                <span class="pill green">
                    ${profileScore === null ? 'Not scored' : profileScore.toFixed(2) + '% Match'}
                </span>

                <span class="pill">
                    ${esc(profile.email || 'Email unavailable')}
                </span>

            </div>

            <section class="profile-evaluation">
                <div class="profile-evaluation-head">
                    <div><span class="muted">Evaluation status</span><div>${evaluationBadge(evaluationStatus)}</div></div>
                    <div><span class="muted">Scoring completeness</span><strong>${evidenceCoverage === null ? 'Unavailable' : evidenceCoverage.toFixed(1) + '%'}</strong></div>
                    <div><span class="muted">Unevaluated weight</span><strong>${unevaluatedWeight === null ? 'Unavailable' : formatNumber(unevaluatedWeight, 1) + '%'}</strong></div>
                    <div><span class="muted">Exact required-skill coverage</span><strong>${requiredSkillStats.coverage === null ? 'Unavailable' : requiredSkillStats.coverage.toFixed(1) + '%'}</strong></div>
                </div>
                ${evidenceCoverage === null ? '<p class="sub">The candidate API did not provide scoring completeness.</p>' : evidenceCoverageHTML(candidate)}
                ${requiredSkillCoverageHTML(candidate)}
                <p class="sub">Scoring completeness measures whether applicable scoring components were evaluated. Required-skill coverage measures exact required skills evidenced in the resume. Related skills are shown separately and are not counted as exact matches.</p>
            </section>


            <hr style="border:0;border-top:1px solid #e5eaf1;margin:20px 0">


            <!-- PROFILE SUMMARY -->

            <h3>Candidate Overview</h3>

            <p>
                ${esc(explanation.summary || 'No summary available.')}
            </p>


            <div class="grid2">

    <div class="panel">
        <div class="muted">Professional Experience</div>
        <h2>${esc(formatExperience(profile.professional_experience_years))}</h2>
    </div>

    <div class="panel">
        <div class="muted">Internship Experience</div>
        <h2>${esc(formatExperience(profile.internship_experience_years))}</h2>
    </div>

    <div class="panel">
        <div class="muted">Stated Experience</div>
        <h2>${esc(formatExperience(profile.stated_experience_years))}</h2>
    </div>

    <div class="panel">
        <div class="muted">Experience Evidence Status</div>
        <strong>${esc(experienceStatus(profile))}</strong>
    </div>

    <div class="panel">
        <div class="muted">Contact</div>
        <strong>${esc(profile.phone || 'Not available')}</strong>
    </div>

</div>




            <!-- SKILLS -->

            <h3>Matched Requirements</h3>

            <div class="requirements">
                ${skillHTML(satisfied)}
            </div>


            <h3>Unverified Requirements</h3>

            <div class="requirements">

                ${
                    unverified.map(skill => `
                        <span class="pill">
                            ${esc(skill)}
                        </span>
                    `).join('') ||
                    '<span class="muted">None identified.</span>'
                }

            </div>


            <h3>Missing Requirements</h3>
            <div class="requirements">
                ${(explanation.missing_skills || []).map(skill => `<span class="pill missing-pill">${esc(skill)}</span>`).join('') || '<span class="muted">No explicit missing requirements reported.</span>'}
            </div>
            <h3>Requirement-Level Evidence</h3>

<p class="sub">
    Each requirement is classified using evidence extracted
    from the candidate's resume.
</p>

${requirementEvidenceHTML}

            <!-- SCORING -->

            <h3>Matching Score Breakdown</h3>

            ${
                breakdownHTML ||
                '<p class="muted">Score breakdown unavailable.</p>'
            }


            <!-- EXPERIENCE -->

            <h3>Experience Evidence</h3>

            <div>

                ${
                    experienceEvidence.length
                        ? experienceEvidence.map(item => `
                            <div style="
                                padding:10px;
                                border-left:3px solid #54b394;
                                margin:8px 0;
                                background:#f8fafc
                            ">
                                ${esc(item)}
                            </div>
                        `).join('')
                        : '<p class="muted">No explicit experience evidence extracted.</p>'
                }

            </div>

            <h3>Internship Evidence</h3>

<div>
    ${
        internshipEvidence.length
            ? internshipEvidence.map(item => `
                <div style="
                    padding:10px;
                    border-left:3px solid #4b8bd8;
                    margin:8px 0;
                    background:#f8fafc
                ">
                    ${esc(item)}
                </div>
            `).join('')
            : '<p class="muted">No internship evidence extracted.</p>'
    }
</div>


            <!-- EDUCATION -->

            <h3>Education</h3>

            <p>
                ${esc(profile.education || 'Education unavailable.')}
            </p>


            <!-- CERTIFICATIONS -->

            <h3>Certifications</h3>

            <div class="requirements">

                ${
                    (profile.certifications || []).map(item => `
                        <span class="pill">
                            ${esc(item)}
                        </span>
                    `).join('') ||
                    '<span class="muted">No certifications extracted.</span>'
                }

            </div>


            <!-- PROJECTS -->

            <h3>Projects</h3>

            <div>

                ${
                    (profile.projects || []).length
                        ? profile.projects.map(project => `
                            <div style="
                                padding:10px;
                                border-bottom:1px solid #eef1f5
                            ">
                                ${esc(
                                    typeof project === 'string'
                                        ? project
                                        : project.title || JSON.stringify(project)
                                )}
                            </div>
                        `).join('')
                        : '<p class="muted">No project details extracted.</p>'
                }

            </div>


            <!-- EXPLAINABLE INTERVIEW GUIDE -->

            <h3>Explainable Match Assessment</h3>
            <p class="muted">
                Component scores show how the configured scoring model evaluated the available resume evidence.
                A high match score is a prioritization signal, not a hiring decision.
            </p>
            <div class="explainability-note">
                <strong>How to interpret this profile</strong>
                <p>${esc(explanation.summary || 'Review the component breakdown and source evidence below.')}</p>
                <p class="muted">Coverage measures applicable scoring weight evaluated. It does not certify the truth of resume claims.</p>
            </div>

            <h3>Suggested Structured Interview Questions</h3>
            <p class="muted">Use these prompts to validate skills or project claims. They are rule-based suggestions from extracted resume/JD evidence, not independently verified findings.</p>
            <div class="interview-question-list">
                ${buildInterviewQuestions(candidate, explanation).map((item, index) => `
                    <article class="interview-question">
                        <div class="interview-question-meta">
                            <span>Question ${index + 1}</span>
                            <b>${esc(item.focus)}</b>
                        </div>
                        <p>${esc(item.question)}</p>
                        <small>${esc(item.signal)}</small>
                    </article>
                `).join('')}
            </div>

            <!-- INTERVIEW VERIFICATION -->

            <h3>Suggested Interview Verification</h3>

            <div class="requirements">

                ${
                    verify.map(skill => `
                        <span class="pill">
                            ${esc(skill)}
                        </span>
                    `).join('') ||
                    '<span class="muted">No specific verification suggestions available.</span>'
                }

            </div>


            <p class="muted" style="margin-top:20px">

                TalentIQ provides decision-support information.
                Extracted information should be verified by a human reviewer.
                An unverified skill is not necessarily an absent skill.

            </p>

        `);

    } catch (error) {

        toast(error.message);

    }

}


// ======================================================
// 17. CANDIDATE COMPARISON
// ======================================================

async function compareSelected() {

    try {

        const ids = [
            ...document.querySelectorAll('.sel:checked')
        ].map(element => Number(element.value));


        if (ids.length < 2) {

            return toast(
                'Select at least two candidates to compare.'
            );

        }


        const result = await api(
            '/api/candidates/compare',
            {

                method: 'POST',

                headers: {
                    'Content-Type': 'application/json'
                },

                body: JSON.stringify({
                    candidate_ids: ids
                })

            }
        );


        const rows = Array.isArray(result) ? result : (result.candidates || []);
        // Normalize comparison evidence before rendering.
// The backend comparison evidence is the source of truth.

rows.forEach(candidate => {
    const evidence = candidate.evidence || {};

    candidate.evidence = {
        matched: Array.isArray(evidence.matched)
            ? evidence.matched
            : [],

        related: Array.isArray(evidence.related)
            ? evidence.related
            : [],

        needs_verification: Array.isArray(evidence.needs_verification)
            ? evidence.needs_verification
            : [],

        missing: Array.isArray(evidence.missing)
            ? evidence.missing
            : []
    };
});


        const dimensions = [

    [
        'Overall Match',
        candidate =>
            candidate.score == null
                ? 'Unknown'
                : candidate.score + '%'
    ],

    [
        'Evaluation Status',
        candidate => {
            const status = getEvaluationStatus(candidate);
            return status === 'unknown'
                ? 'Not supplied'
                : status.replaceAll('_', ' ');
        }
    ],

    [
        'Evidence Coverage',
        candidate => {
            const coverage = getEvidenceCoverage(candidate);
            return coverage === null
                ? 'Unavailable'
                : formatNumber(coverage, 1) + '%';
        }
    ],

    [
    'Experience',
    candidate => {
        const professional = candidate.professional_experience_years;
        const internship = candidate.internship_experience_years;

        const parts = [];

        parts.push(
            `Professional: ${professional == null
                ? 'Not established'
                : professional + ' yrs'}`
        );

        parts.push(
            `Internship: ${internship == null
                ? 'Not established'
                : internship + ' yrs'}`
        );

        return parts.join(' | ');
    }
],

    [
        'Matched Skills',
        candidate =>
            candidate.evidence?.matched?.join(', ') || '—'
    ],

    [
        'Related Skills',
        candidate =>
            candidate.evidence?.related?.join(', ') || '—'
    ],

    [
        'Needs Verification',
        candidate =>
            candidate.evidence?.needs_verification?.join(', ') || '—'
    ],

    [
        'Missing Skills',
        candidate =>
            candidate.evidence?.missing?.join(', ') || '—'
    ]

];


        // Score component comparison

        const componentKeys = [
            ...new Set(
                rows.flatMap(candidate =>
                    Object.keys(candidate.component_scores || {})
                )
            )
        ];


        componentKeys.forEach(key => {

            dimensions.push([

                key.replaceAll('_', ' '),

                candidate =>
                    candidate.component_scores?.[key] == null
                        ? '—'
                        : candidate.component_scores[key] + '%'

            ]);

        });


        showModal(`

            <button
                class="close"
                onclick="closeModal()"
            >
                Close
            </button>


            <h2>Candidate Comparison</h2>

            <p class="muted">
                Compare candidate evidence, skills and score components.
            </p>


            <div class="tablewrap">

                <table>

                    <thead>

                        <tr>

                            <th>Dimension</th>

                            ${rows.map(candidate => `
                                <th>
                                    ${esc(candidate.name)}
                                </th>
                            `).join('')}

                        </tr>

                    </thead>


                    <tbody>

                        ${dimensions.map(([label, formatter]) => `

                            <tr>

                                <td>
                                    ${esc(label)}
                                </td>

                                ${rows.map(candidate => `

                                    <td>
                                        ${esc(formatter(candidate))}
                                    </td>

                                `).join('')}

                            </tr>

                        `).join('')}

                    </tbody>

                </table>

            </div>


            <h3>Skill Coverage Matrix</h3>


            <div class="tablewrap">

                <table>

                    <thead>

                        <tr>

                            <th>Skill</th>

                            ${rows.map(candidate => `
                                <th>${esc(candidate.name)}</th>
                            `).join('')}

                        </tr>

                    </thead>


                    <tbody>

                        ${(result.skill_matrix || []).map(item => `

                            <tr>

                                <td>
                                    ${esc(item.skill)}
                                </td>

                                ${rows.map(candidate => `

                                    <td>
                                        ${
                                            item.candidates?.[candidate.candidate_id]
                                                ? '✓'
                                                : '—'
                                        }
                                    </td>

                                `).join('')}

                            </tr>

                        `).join('')}

                    </tbody>

                </table>

            </div>


            <p class="muted">
                ${esc(result.comparison_note || '')}
            </p>


            <p class="muted">
                Comparison is decision support, not an automated hiring decision.
            </p>

        `);

    } catch (error) {

        toast(error.message);

    }

}


// ======================================================
// 18. RANKING EXPLANATION
// ======================================================

async function showRankingExplanation() {

    try {

        const jobId = $('jobpick').value;

        if (!jobId) {
            return toast('Select a job first.');
        }


        const result = await api(
            `/api/jobs/${jobId}/ranking/explanation`
        );


        const rows = result.ranking_explanations || [];


        showModal(`

            <button
                class="close"
                onclick="closeModal()"
            >
                Close
            </button>


            <h2>Ranking Explanation</h2>


            <p class="muted">
                ${result.candidate_count || rows.length}
                candidates analyzed.
            </p>


            ${
                rows.length

                    ? rows.map(candidate => `

                        <div style="
                            padding:15px 0;
                            border-bottom:1px solid #eef1f5
                        ">


                            <div style="
                                display:flex;
                                justify-content:space-between;
                                gap:12px
                            ">

                                <strong>
                                    #${candidate.rank} · ${esc(candidate.name)}
                                </strong>

                                <span class="score">
                                    ${
                                        candidate.score == null
                                            ? '—'
                                            : candidate.score + '%'
                                    }
                                </span>

                            </div>


                            <p class="muted">
                                ${esc(candidate.comparison_to_previous)}
                            </p>


                            <div class="requirements">

                                ${
                                    Object.entries(
                                        candidate.evidence_summary || {}
                                    ).map(([key, value]) => `

                                        <span class="pill">
                                            ${esc(key.replaceAll('_', ' '))}
                                            · ${esc(value)}
                                        </span>

                                    `).join('')
                                }

                            </div>


                            <div class="requirements">

                                ${
                                    Object.entries(
                                        candidate.component_scores || {}
                                    ).map(([key, value]) => `

                                        <span class="pill green">
                                            ${esc(key.replaceAll('_', ' '))}
                                            · ${esc(value)}%
                                        </span>

                                    `).join('')
                                }

                            </div>


                            <p class="sub">
                                ${esc(candidate.interpretation)}
                            </p>


                        </div>

                    `).join('')

                    : '<p class="muted">No candidates available.</p>'

            }


            <p class="muted">
                ${esc(result.note || '')}
            </p>

        `);

    } catch (error) {

        toast(error.message);

    }

}


// ======================================================
// 19. RANKING EVALUATION
// ======================================================

async function evaluateRanking() {

    try {

        const jobId = $('jobpick').value;

        if (!jobId) {
            return toast('Select a job first.');
        }

        const relevantInput = prompt(
            'Enter relevant candidate IDs separated by commas. Use independent human relevance labels.'
        );

        if (relevantInput === null) return;

        const relevantIds = relevantInput
            .split(',')
            .map(value => Number(value.trim()))
            .filter(Number.isFinite);

        if (!relevantIds.length) {
            return toast('Enter at least one valid candidate ID.');
        }

        const result = await api(
            `/api/jobs/${jobId}/ranking/evaluation`,
            {
                method: 'POST',

                headers: {
                    'Content-Type': 'application/json'
                },

                body: JSON.stringify({
                    relevant_candidate_ids: relevantIds
                })
            }
        );

        showModal(`

            <button class="close" onclick="closeModal()">
                Close
            </button>

            <h2>Ranking Evaluation</h2>

            <p class="muted">
                Evaluation against independently supplied relevance labels.
            </p>

            <div class="grid2">

                ${Object.entries(result.metrics || result).map(([key, value]) => `

                    <div class="panel">

                        <div class="muted">
                            ${esc(key.replaceAll('_', ' '))}
                        </div>

                        <h2>
                            ${esc(
                                typeof value === 'number'
                                    ? formatNumber(value, 4)
                                    : JSON.stringify(value)
                            )}
                        </h2>

                    </div>

                `).join('')}

            </div>

        `);

    } catch (error) {

        toast(error.message);

    }

}


// ======================================================
// 20. DELETE CANDIDATE
// ======================================================

async function removeCandidate(id) {

    if (!confirm(
        'Delete this resume and its candidate record?'
    )) {
        return;
    }

    try {

        await api(`/api/resumes/${id}`, {
            method: 'DELETE'
        });

        await loadResults();

        toast('Candidate deleted successfully.');

    } catch (error) {

        toast(error.message);

    }

}


// ======================================================
// RECALCULATE EXISTING CANDIDATES
// ======================================================

async function recalculateCandidates() {
    const id = $('jobpick').value;
    if (!id) return toast('Select a job first.');
    if (!confirm('Recalculate every candidate for this role using the current scoring engine?')) return;

    const button = $('recalculate-button');
    if (button) {
        button.disabled = true;
        button.textContent = 'Recalculating…';
    }

    try {
        const result = await api(`/api/jobs/${encodeURIComponent(id)}/recalculate`, { method: 'POST' });
        await loadResults();
        toast(`Recalculated ${result.recalculated} of ${result.total_candidates} candidates; ${result.failed} failed.`);
        showModal(`
            <button class="close" onclick="closeModal()">Close</button>
            <div class="eyebrow">Scoring refresh</div>
            <h2>Recalculation complete</h2>
            <div class="recalc-summary-grid">
                <div><strong>${esc(result.total_candidates)}</strong><span>Total candidates</span></div>
                <div><strong>${esc(result.recalculated)}</strong><span>Recalculated</span></div>
                <div><strong>${esc(result.failed)}</strong><span>Failed</span></div>
            </div>
            <h3>Evaluation summary</h3>
            <div class="requirements">
                ${Object.entries(result.evaluation_summary || {}).map(([key, value]) => `<span class="pill">${esc(key.replaceAll('_', ' '))}: ${esc(value)}</span>`).join('')}
            </div>
            ${(result.failures || []).length ? `<h3>Failures</h3><ul>${result.failures.map(item => `<li>${esc(item.filename || item.candidate_id)}: ${esc(item.error || 'Unknown error')}</li>`).join('')}</ul>` : '<p class="muted">No candidate recalculation failures.</p>'}
        `);
    } catch (error) {
        toast(error.message);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = 'Recalculate scores';
        }
    }
}


// ======================================================
// 21. CSV EXPORT
// ======================================================

function exportCsv() {

    const id = $('jobpick').value;

    if (!id) {
        return toast('Select a job first.');
    }

    window.location.href =
        `/api/candidates/export/${id}`;

}


// ======================================================
// 22. PAGE NAVIGATION
// ======================================================

const pageTitles = {

    overview: 'Candidate Overview',

    jobs: 'Job Descriptions',

    resumes: 'Resume Processing',

    settings: 'Workspace Settings'

};


function switchPage(pageName) {

    const selectedPage = $(`page-${pageName}`);

    if (!selectedPage) return;


    // Hide all pages

    document.querySelectorAll('.page').forEach(page => {

        page.classList.remove('active');

    });


    // Reset sidebar

    document.querySelectorAll('.nav').forEach(button => {

        button.classList.remove('on');

    });


    // Activate page

    selectedPage.classList.add('active');


    // Update heading

    $('page-title').textContent =
        pageTitles[pageName] || 'TalentIQ';


    // Highlight sidebar

    const selectedButton = document.querySelector(
        `.nav[data-page="${pageName}"]`
    );

    if (selectedButton) {
        selectedButton.classList.add('on');
    }


    // Reset scroll

    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });


    // Refresh overview

    if (pageName === 'overview') {

        loadResults().catch(error => toast(error.message));

    } else if (pageName === 'jobs') {

        renderJDInsights();

    }

}


// ======================================================
// 23. SIDEBAR EVENTS
// ======================================================

document.querySelectorAll('.nav[data-page]').forEach(button => {

    button.addEventListener('click', () => {

        switchPage(button.dataset.page);

    });

});


// ======================================================
// 24. MODAL EVENTS
// ======================================================

document.addEventListener('keydown', event => {

    if (event.key === 'Escape') {
        closeModal();
    }

});


// ======================================================
// 25. APPLICATION START
// ======================================================

init().catch(error => {

    console.error('TalentIQ initialization failed:', error);

    toast(error.message || 'Unable to initialize TalentIQ.');

});