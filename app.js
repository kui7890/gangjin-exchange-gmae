const state = {
  quests: [],
  leaderboard: [],
  selectedTeamId: 1,
};

const teamSelect = document.querySelector("#team-select");
const refreshButton = document.querySelector("#refresh-button");
const resetButton = document.querySelector("#reset-button");
const questGrid = document.querySelector("#quest-grid");
const leaderboardList = document.querySelector("#leaderboard-list");
const feedbackText = document.querySelector("#feedback-text");
const currentTeamName = document.querySelector("#current-team-name");
const currentTeamScore = document.querySelector("#current-team-score");
const questTemplate = document.querySelector("#quest-template");

const fetchJson = async (url, options = {}) => {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "요청을 처리하지 못했습니다.");
  }

  return data;
};

const updateCurrentTeamCard = () => {
  const currentTeam = state.leaderboard.find(
    (team) => Number(team.id) === Number(state.selectedTeamId),
  );

  currentTeamName.textContent = currentTeam ? currentTeam.name : `${state.selectedTeamId}모둠`;
  currentTeamScore.textContent = currentTeam ? `${currentTeam.score}점` : "0점";
};

const renderLeaderboard = () => {
  leaderboardList.innerHTML = "";

  state.leaderboard.forEach((team, index) => {
    const item = document.createElement("li");
    item.className = "leaderboard-item";
    item.innerHTML = `
      <span class="leaderboard-rank">${index + 1}</span>
      <div>
        <strong>${team.name}</strong>
        <span>${team.completedCount}개 퀘스트 해결</span>
      </div>
      <span class="leaderboard-points">${team.score}점</span>
    `;

    leaderboardList.appendChild(item);
  });

  updateCurrentTeamCard();
};

const makeStatusText = (quest) => {
  if (quest.solvedBySelectedTeam) {
    return "이미 우리 모둠이 해결한 퀘스트예요.";
  }

  return "아직 도전 가능해요.";
};

const renderQuests = () => {
  questGrid.innerHTML = "";

  state.quests.forEach((quest) => {
    const card = questTemplate.content.firstElementChild.cloneNode(true);

    card.dataset.questId = quest.id;
    card.querySelector(".quest-region").textContent = quest.region;
    card.querySelector(".quest-points").textContent = `${quest.points}점`;
    card.querySelector(".quest-title").textContent = quest.title;
    card.querySelector(".quest-exchange").textContent = `교류 단서: ${quest.exchange}`;
    card.querySelector(".quest-question").textContent = quest.question;

    const optionsWrap = card.querySelector(".quest-options");
    quest.options.forEach((option) => {
      const label = document.createElement("label");
      label.className = "quest-option";
      label.innerHTML = `
        <input type="radio" name="answer-${quest.id}" value="${option.id}" />
        <span>${option.text}</span>
      `;
      optionsWrap.appendChild(label);
    });

    const status = card.querySelector(".quest-status");
    status.textContent = makeStatusText(quest);
    status.className = `quest-status ${quest.solvedBySelectedTeam ? "status-warning" : ""}`;

    const submitButton = card.querySelector("button[type='submit']");
    submitButton.disabled = Boolean(quest.solvedBySelectedTeam);

    const form = card.querySelector(".quest-form");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const selected = form.querySelector("input[type='radio']:checked");
      if (!selected) {
        setFeedback("답을 하나 고른 뒤 제출해 주세요.", "status-error");
        return;
      }

      submitButton.disabled = true;

      try {
        const result = await fetchJson("/api/submit", {
          method: "POST",
          body: JSON.stringify({
            teamId: state.selectedTeamId,
            questId: quest.id,
            answer: selected.value,
          }),
        });

        state.leaderboard = result.leaderboard;

        if (result.correct && result.awardedPoints > 0) {
          quest.solvedBySelectedTeam = true;
          status.textContent = `정답! ${result.awardedPoints}점을 얻었어요.`;
          status.className = "quest-status status-success";
        } else if (result.correct) {
          quest.solvedBySelectedTeam = true;
          status.textContent = "이미 해결한 퀘스트라 점수는 그대로예요.";
          status.className = "quest-status status-warning";
        } else {
          status.textContent = `다시 생각해 보세요. 정답은 ${result.correctAnswerLabel}였어요.`;
          status.className = "quest-status status-error";
          submitButton.disabled = false;
        }

        setFeedback(result.message, result.correct ? "status-success" : "status-error");
        renderLeaderboard();
      } catch (error) {
        submitButton.disabled = false;
        setFeedback(error.message, "status-error");
      }
    });

    questGrid.appendChild(card);
  });
};

const setFeedback = (text, statusClass = "") => {
  feedbackText.textContent = text;
  feedbackText.className = statusClass;
};

const loadLeaderboard = async () => {
  const data = await fetchJson("/api/leaderboard");
  state.leaderboard = data.leaderboard;
  renderLeaderboard();
};

const loadQuests = async () => {
  const data = await fetchJson(`/api/quests?teamId=${state.selectedTeamId}`);
  state.quests = data.quests;
  renderQuests();
};

const refreshAll = async () => {
  refreshButton.disabled = true;
  try {
    await Promise.all([loadLeaderboard(), loadQuests()]);
  } catch (error) {
    setFeedback(error.message, "status-error");
  } finally {
    refreshButton.disabled = false;
  }
};

teamSelect.addEventListener("change", async (event) => {
  state.selectedTeamId = Number(event.target.value);
  updateCurrentTeamCard();
  await loadQuests();
});

refreshButton.addEventListener("click", refreshAll);

resetButton.addEventListener("click", async () => {
  const confirmed = window.confirm("모든 모둠 점수와 해결 기록을 초기화할까요?");
  if (!confirmed) {
    return;
  }

  try {
    const result = await fetchJson("/api/reset", {
      method: "POST",
      body: JSON.stringify({ confirm: true }),
    });
    state.leaderboard = result.leaderboard;
    setFeedback(result.message, "status-warning");
    await loadQuests();
    renderLeaderboard();
  } catch (error) {
    setFeedback(error.message, "status-error");
  }
});

refreshAll();
