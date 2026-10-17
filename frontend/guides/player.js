const $ = (s) => document.querySelector(s);
const data = {
  zoho: [
    "Find your Zoho organization ID, choose its data center, grant invoice READ access, then preview and confirm.",
    "https://www.zoho.com/invoice/api/v3/oauth/",
  ],
  razorpay: [
    "Choose Test Mode, open Account & Settings / API Keys, save test credentials privately, then preview.",
    "https://razorpay.com/docs/api/authentication/",
  ],
  stripe: [
    "Choose a sandbox, create a restricted test key with invoice READ permission, then preview remaining balances.",
    "https://docs.stripe.com/keys",
  ],
};
function timeline() {
  return $("#film").contentWindow.__timelines?.main;
}
function update() {
  $("#mp4").pause();
  $("#mp4").src = $("#provider").value + ".mp4";
  $("#download-mp4").href = $("#provider").value + ".mp4";
  const current = data[$("#provider").value];
  $("#summary").textContent = current[0];
  $("#docs").href = current[1];
}
$("#provider").onchange = () => {
  $("#film").src = $("#provider").value + "/index.html";
  $("#seek").value = 0;
  update();
};
function fit() {
  const frame = $("#film");
  frame.style.width = "1280px";
  frame.style.height = "720px";
  frame.style.transformOrigin = "top left";
  frame.style.transform =
    "scale(" + frame.parentElement.clientWidth / 1280 + ")";
}
new ResizeObserver(fit).observe($("#film").parentElement);
$("#film").onload = () => {
  fit();
  timeline()?.pause().seek(0.8);
};
$("#play").onclick = () => timeline()?.play();
$("#pause").onclick = () => timeline()?.pause();
$("#restart").onclick = () => timeline()?.restart();
$("#seek").oninput = () =>
  timeline()
    ?.pause()
    .seek(Number($("#seek").value));
setInterval(() => {
  const tl = timeline();
  if (tl) {
    $("#seek").value = tl.time();
    $("#time").textContent = Math.floor(tl.time()) + " / 40s";
  }
}, 100);
update();

$("#toggle-player").onclick = () => {
  const interactive = $("#film").hidden;
  $("#film").hidden = !interactive;
  $("#interactive-controls").hidden = !interactive;
  $("#mp4").hidden = interactive;
  $("#mp4").pause();
  timeline()?.pause();
  $("#toggle-player").textContent = interactive
    ? "Watch MP4 video"
    : "Use interactive guide";
  fit();
};
