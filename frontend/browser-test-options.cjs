// Default to Playwright's installed Chromium. Explicit overrides support local
// Edge installations and isolated portable browser runtimes without code edits.
module.exports=function browserTestOptions(){
 const options={headless:true};
 if(process.env.PLAYWRIGHT_BROWSER_CHANNEL)options.channel=process.env.PLAYWRIGHT_BROWSER_CHANNEL;
 if(process.env.PLAYWRIGHT_EXECUTABLE_PATH)options.executablePath=process.env.PLAYWRIGHT_EXECUTABLE_PATH;
 if(process.env.PLAYWRIGHT_BROWSER_ARGS){
  const args=JSON.parse(process.env.PLAYWRIGHT_BROWSER_ARGS);
  if(!Array.isArray(args)||args.some(arg=>typeof arg!=='string'))throw new Error('PLAYWRIGHT_BROWSER_ARGS must be a JSON string array');
  options.args=args;
 }
 return options;
};
