document.addEventListener("DOMContentLoaded", function () {
    const chainSelect = document.querySelector("select[name='chain']");

    const tronBox = document.getElementById("tron-action-box");
    const ethBox = document.getElementById("eth-box");
    const btcBox = document.getElementById("btc-box");

    function toggleDepositUI() {
        const chain = chainSelect.value;

        tronBox.classList.add("d-none");
        ethBox.classList.add("d-none");
        btcBox.classList.add("d-none");

        if (chain === "tron") {
            tronBox.classList.remove("d-none");
        } else if (chain === "ethereum") {
            ethBox.classList.remove("d-none");
        } else if (chain === "bitcoin") {
            btcBox.classList.remove("d-none");
        }
    }

    chainSelect.addEventListener("change", toggleDepositUI);
});
