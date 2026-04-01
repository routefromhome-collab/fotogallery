const gallery = document.getElementById("gallery");
const viewer = document.getElementById("viewer");
const full = document.getElementById("full");

async function loadImages() {
    const res = await fetch("/images");
    const images = await res.json();

    images.forEach(name => {
        const div = document.createElement("div");
        div.className = "skeleton";
        gallery.appendChild(div);

        const img = document.createElement("img");
        img.dataset.name = name;
        img.onload = () => div.replaceWith(img);
        img.src = `/image?name=${encodeURIComponent(name)}`;
        img.onclick = () => {
            full.src = img.src;
            viewer.style.display = "flex";
        }
    });
}

function closeViewer() {
    viewer.style.display = "none";
    full.src = "";
}
img.onerror = () => {
    div.remove(); // удаляем битую картинку
};
document.addEventListener("DOMContentLoaded", loadImages);