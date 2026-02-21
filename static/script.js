/* ============================================================
   NFL Stats Showdown — Quiz Interactivity
   ============================================================ */

let currentQuestion = 0;
let score = 0;
let isAnswering = false;

document.addEventListener("DOMContentLoaded", () => {
    loadQuestion(0);
});

async function loadQuestion(n) {
    isAnswering = false;

    // Reset card states
    const card1 = document.getElementById("card-1");
    const card2 = document.getElementById("card-2");
    card1.className = "player-card";
    card2.className = "player-card";

    // Hide results overlays
    document.getElementById("result-1").classList.remove("show");
    document.getElementById("result-2").classList.remove("show");

    // Hide feedback
    const banner = document.getElementById("feedback-banner");
    banner.className = "feedback-banner";

    // Set loading state
    document.getElementById("question-text").textContent = "Loading...";

    try {
        const resp = await fetch(`/api/question/${n}`);
        if (!resp.ok) {
            // Quiz might be over or invalid
            window.location.href = "/results";
            return;
        }
        const data = await resp.json();

        // Update progress
        document.getElementById("question-counter").textContent =
            `Question ${n + 1} of ${data.total}`;
        const pct = ((n) / data.total) * 100;
        document.getElementById("progress-bar").style.width = `${pct}%`;

        // Set question text
        document.getElementById("question-text").innerHTML =
            `Who had <span class="stat-highlight">${data.question_word} ${data.stat_display}</span> in <span class="season-highlight">${data.season}</span>?`;

        // Player 1
        document.getElementById("player1-img").src = data.player1.headshot;
        document.getElementById("player1-name").textContent = data.player1.name;
        document.getElementById("player1-team").textContent = data.player1.team;

        // Player 2
        document.getElementById("player2-img").src = data.player2.headshot;
        document.getElementById("player2-name").textContent = data.player2.name;
        document.getElementById("player2-team").textContent = data.player2.team;

        currentQuestion = n;
    } catch (err) {
        console.error("Error loading question:", err);
        document.getElementById("question-text").textContent =
            "Error loading question. Please refresh.";
    }
}

async function submitAnswer(choice) {
    if (isAnswering) return;
    isAnswering = true;

    const card1 = document.getElementById("card-1");
    const card2 = document.getElementById("card-2");

    // Disable clicks
    card1.classList.add("disabled");
    card2.classList.add("disabled");

    try {
        const resp = await fetch(`/api/answer/${currentQuestion}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ answer: choice }),
        });

        const data = await resp.json();

        // Update score
        score = data.score;
        document.getElementById("score-display").textContent = `Score: ${score}`;

        // Show stat values on both cards
        const result1 = document.getElementById("result-1");
        const result2 = document.getElementById("result-2");

        document.getElementById("value-1").textContent = data.player1_value;
        document.getElementById("label-1").textContent = data.stat_display;
        document.getElementById("value-2").textContent = data.player2_value;
        document.getElementById("label-2").textContent = data.stat_display;

        result1.classList.add("show");
        result2.classList.add("show");

        // Highlight correct/wrong
        const correctCard = data.correct_answer === 1 ? card1 : card2;
        const wrongCard = data.correct_answer === 1 ? card2 : card1;

        correctCard.classList.add("correct", "winner");
        if (!data.is_correct) {
            const userCard = choice === 1 ? card1 : card2;
            userCard.classList.add("wrong");
        }

        // Feedback banner
        const banner = document.getElementById("feedback-banner");
        const fbIcon = document.getElementById("feedback-icon");
        const fbText = document.getElementById("feedback-text");

        if (data.is_correct) {
            banner.className = "feedback-banner show correct";
            fbIcon.textContent = "✅";
            fbText.textContent = "Correct!";
        } else {
            banner.className = "feedback-banner show wrong";
            fbIcon.textContent = "❌";
            fbText.textContent = "Wrong!";
        }

        // Wait 3 seconds then advance
        setTimeout(() => {
            const next = currentQuestion + 1;
            if (next >= TOTAL_QUESTIONS) {
                // Update progress to full
                document.getElementById("progress-bar").style.width = "100%";
                setTimeout(() => {
                    window.location.href = "/results";
                }, 300);
            } else {
                loadQuestion(next);
            }
        }, 3000);

    } catch (err) {
        console.error("Error submitting answer:", err);
        isAnswering = false;
        card1.classList.remove("disabled");
        card2.classList.remove("disabled");
    }
}
