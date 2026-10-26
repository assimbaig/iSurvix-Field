const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const scripts=fs.readdirSync(__dirname).filter(name=>/^check-.*\.cjs$/.test(name)).sort();
let failed=0;
for(const script of scripts){
 console.log(`\nRunning ${script}`);
 const result=spawnSync(process.execPath,[path.join(__dirname,script)],{cwd:__dirname,stdio:'inherit',env:process.env});
 if(result.error||result.status!==0){failed++;if(result.error)console.error(result.error.message);}
}
console.log(`Frontend scripts: ${scripts.length-failed}/${scripts.length} passed`);
process.exitCode=failed?1:0;
