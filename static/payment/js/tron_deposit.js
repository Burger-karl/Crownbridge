document.addEventListener("DOMContentLoaded", () => {
  const chainSelect = document.querySelector("select[name='chain']");
  const tronBox = document.getElementById("tron-action-box");
  const sendBtn = document.getElementById("tron-send-btn");

  if (!chainSelect || !tronBox) return;

  function toggleTronBox() {
    if (chainSelect.value === "TRON") {
      tronBox.classList.remove("d-none");
    } else {
      tronBox.classList.add("d-none");
    }
  }

  chainSelect.addEventListener("change", toggleTronBox);
  toggleTronBox();

  sendBtn?.addEventListener("click", async () => {
    if (!window.tronWeb || !window.tronWeb.ready) {
      alert("Please install and unlock TronLink");
      return;
    }

    const amountInput = document.querySelector("input[name='amount']");
    const amount = amountInput?.value;
    const receiver = sendBtn.dataset.platformWallet;
    const confirmUrl = sendBtn.dataset.confirmUrl;
    const depositId = document.getElementById("deposit-id")?.value;

    if (!amount || !receiver || !depositId) {
      alert("Deposit intent not created yet.");
      return;
    }

    try {
      const tx = await tronWeb.trx.sendTransaction(
        receiver,
        tronWeb.toSun(amount)
      );

      const res = await fetch(confirmUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          tx_hash: tx.txid,
          deposit_id: depositId,
        }),
      });

      const data = await res.json();

      if (data.success) {
        alert("Deposit submitted successfully");
        window.location.href = "/payment/deposit-history/";
      } else {
        alert(data.error || "Deposit verification pending");
      }
    } catch (err) {
      console.error(err);
      alert("Transaction cancelled or failed");
    }
  });
});

// CSRF helper
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
