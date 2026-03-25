// Array.prototype.at polyfill for older browsers
if (!Array.prototype.at) {
  Array.prototype.at = function(index: number) {
    const len = this.length;
    if (index < 0) {
      index = len + index;
    }
    if (index < 0 || index >= len) {
      return undefined;
    }
    return this[index];
  };
}
