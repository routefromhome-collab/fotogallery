let allImages=[], offset=0, limit=10, loading=false;

async function fetchImages(){
    if(loading) return;
    loading=true;
    const gallery=document.getElementById("gallery");
    for(let i=0;i<limit;i++){
        const skel=document.createElement("div");
        skel.className="skeleton";
        gallery.appendChild(skel);
    }
    const res=await fetch("/images");
    const data=await res.json();
    allImages=data;
    document.querySelectorAll(".skeleton").forEach(s=>s.remove());
    loadNextBatch();
    loading=false;
}

function loadNextBatch(){
    const gallery=document.getElementById("gallery");
    const batch=allImages.slice(offset,offset+limit);
    batch.forEach(name=>{
        const card=document.createElement("div");
        card.className="card";
        const img=document.createElement("img");
        img.dataset.name=name;
        img.loading="lazy";
        img.src=`/image?name=${name}`;
        img.onclick=()=>openViewer(img.src);
        card.appendChild(img);
        gallery.appendChild(card);
    });
    offset+=limit;
}

window.addEventListener("scroll",()=>{
    if(window.innerHeight+window.scrollY>=document.body.offsetHeight-300){
        loadNextBatch();
    }
});

function openViewer(src){
    document.getElementById("viewer").style.display="flex";
    document.getElementById("full").src=src;
}
function closeViewer(){
    document.getElementById("viewer").style.display="none";
}

fetchImages();