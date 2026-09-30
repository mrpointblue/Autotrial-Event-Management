function fitVehicleCards(){
  document.querySelectorAll('.vehicle-id-card').forEach(card=>{
    const body=card.querySelector('.vehicle-id-body');body.style.zoom='1';
    const available=card.clientHeight-card.querySelector('header').offsetHeight-2;
    const ratio=Math.min(1,available/body.getBoundingClientRect().height);
    body.style.zoom=String(ratio);
  });
}
window.addEventListener('load',fitVehicleCards);
function fitClassReports() {
  fitVehicleCards();
  // A4 landscape has 186 mm of printable height with 12 mm margins.
  const ruler=document.createElement('div');
  ruler.style.cssText='width:271mm;height:184mm;position:absolute;visibility:hidden';
  document.body.append(ruler);
  const {height,width}=ruler.getBoundingClientRect();
  document.querySelectorAll('.class-report-content').forEach(content=>{
    content.style.zoom='1';
    // Fix the unscaled width before zooming so layout cannot expand to compensate.
    const availableWidth=Math.min(width,content.parentElement.clientWidth);
    content.style.width=availableWidth+'px';
    const bounds=content.getBoundingClientRect();
    const ratio=Math.min(1,height/bounds.height,availableWidth/Math.max(bounds.width,content.scrollWidth));
    content.style.zoom=String(ratio);
  });
  ruler.remove();
}
window.addEventListener('beforeprint',fitClassReports);
document.getElementById('print-button').addEventListener('click',async()=>{
  await Promise.all(Array.from(document.images,img=>img.decode().catch(()=>{})));
  fitClassReports();window.print();
});
