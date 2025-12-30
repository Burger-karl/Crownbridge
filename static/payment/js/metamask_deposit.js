document.addEventListener("DOMContentLoaded", () => {
  const ethBtn = document.getElementById("eth-send-btn");
  if (!ethBtn) return;

  ethBtn.addEventListener("click", async () => {
    if (!window.ethereum) {
      alert("Please install MetaMask");
      return;
    }

    const amount = document.querySelector("input[name='amount']").value;
    const receiver = ethBtn.dataset.wallet;

    try {
      await ethereum.request({ method: "eth_requestAccounts" });

      const provider = new ethers.BrowserProvider(window.ethereum);
      const signer = await provider.getSigner();

      const tx = await signer.sendTransaction({
        to: receiver,
        value: ethers.parseEther(amount)
      });

      await fetch("/payment/confirm-eth-deposit/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({
          tx_hash: tx.hash
        })
      });

      alert("Deposit submitted successfully");
      window.location.href = "/payment/deposit-history/";

    } catch (err) {
      console.error(err);
      alert("Transaction cancelled or failed");
    }
  });
});

function getCookie(name) {
  return document.cookie
    .split("; ")
    .find(row => row.startsWith(name + "="))
    ?.split("=")[1];
}
