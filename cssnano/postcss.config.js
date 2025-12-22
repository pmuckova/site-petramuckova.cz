module.exports = (ctx) => {
  return {
    plugins: [
      // 1. Autoprefixer: Adds vendor prefixes (e.g., -webkit-, -moz-)
      // It uses your package.json "browserslist" to know what to support.
      require('autoprefixer')(),

      require('cssnano')({
        preset: ['default', {

          // A. COMMENTS: Remove all comments to save space.
          // Default leaves some "license" comments (/*! ... */).
          discardComments: {
            removeAll: true,
          },

          // B. SORTING: Organize CSS properties logically.
          // 'concentric-css' orders properties from outside the box to inside
          // (Positioning -> Box Model -> Typography -> Visuals).
          // This compresses better (gzip) and is cleaner.
          cssDeclarationSorter: {
            order: 'concentric-css',
          },

          // C. SAFETY: Prevent z-index rebasing.
          // Sometimes cssnano tries to change z-index: 1000 to z-index: 1
          // to save bytes. This is dangerous if you have 3rd party scripts.
          // We disable this optimization to be safe.
          zindex: false,

          // D. NORMALIZATION: Ensure colors/weights are minimized
          // (e.g., bold -> 700, #ffffff -> #fff)
          colormin: true,
          convertValues: true,
        }]
      })
    ],
  };
};
