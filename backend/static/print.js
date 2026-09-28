function fitClassReports() {
  // A4 landscape has 186 mm of printable height with 12 mm margins.
  const ruler=document.createElement('div');
  ruler.style.cssText='height:184mm;position:absolute;visibility:hidden';
  document.body.append(ruler);
  const height=ruler.getBoundingClientRect().height;
  document.querySelectorAll('.class-report-content').forEach(content=>{
    content.style.zoom='1';
    const ratio=Math.min(1,height/content.getBoundingClientRect().height);
    content.style.zoom=String(ratio);
  });
  ruler.remove();
}
window.addEventListener('beforeprint',fitClassReports);
document.getElementById('print-button').addEventListener('click',async()=>{
  await Promise.all(Array.from(document.images,img=>img.decode().catch(()=>{})));
  fitClassReports();window.print();
});
