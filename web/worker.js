/* Original worker entry point. Bundled with core.js for offline file:// use. */
self.onmessage=async event=>{
  try{
    const {op,bytes,recipe,ids}=event.data;
    const project=OffDayCore.parseProject(bytes);
    if(op==='load'){
      const inventory=await OffDayCore.inventory(project);
      self.postMessage({ok:true,result:{resources:inventory.resources.map(({id,name})=>({id,name})),intervalCount:inventory.existing_interval_count}});
    }else if(op==='preview'){
      const receipt=await OffDayCore.preview(project,OffDayCore.parseRecipe(recipe),ids);
      const output=OffDayCore.apply(project,receipt);
      self.postMessage({ok:true,result:{receipt,output}},[output.buffer]);
    }else throw new Error('Unsupported worker operation');
  }catch(error){self.postMessage({ok:false,error:String(error.message||error).slice(0,2048)});}
};
