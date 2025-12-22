const {execSync} = require('child_process');

// Get the language code from the arguments (e.g., "cs")
const lang = process.argv[2];

if (!lang) {
    console.error("❌ Error: You must provide a language code.");
    console.error("Example: npm run minify-lang -- cs");
    process.exit(1);
}

console.log(`🔧 Minifying HTML for language: [${lang}]`);

try {
    // sitemap?
    if (lang === 'sitemap') {
        const cmdIndex = `html-minifier-terser -c html-config.json -o ../release/sitemap.xml ../sitemap.xml`;
        execSync(cmdIndex, {stdio: 'inherit'});
    } else {
        // Command 1: Index
        const cmdIndex = `html-minifier-terser -c html-config.json -o ../release/${lang}/index.html ../${lang}/index.html`;
        execSync(cmdIndex, {stdio: 'inherit'});

        // Command 2: Blog
        const cmdBlog = `html-minifier-terser -c html-config.json -o ../release/${lang}/blog.html ../${lang}/blog.html`;
        execSync(cmdBlog, {stdio: 'inherit'});

        console.log(`✅ Success for [${lang}]`);
    }

} catch (error) {
    console.error(`❌ Failed to minify [${lang}]`);
    process.exit(1);
}
